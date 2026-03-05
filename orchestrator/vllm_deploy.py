"""vLLM 部署管理"""
import asyncio
import subprocess
import sys
import time
from typing import Optional

import aiohttp

from orchestrator.vllm_config import VLLMConfig


class VLLMDeploymentError(Exception):
    """vLLM 部署错误"""
    pass


class VLLMDeployer:
    """vLLM 部署器"""
    
    def __init__(self, config: Optional[VLLMConfig] = None):
        """初始化部署器
        
        Args:
            config: vLLM 配置，默认使用标准配置
        """
        self.config = config or VLLMConfig()
        self.process: Optional[subprocess.Popen] = None
    
    def check_nvidia_driver(self) -> bool:
        """检查 NVIDIA 驱动是否已安装
        
        Returns:
            True 如果驱动已安装
            
        Raises:
            VLLMDeploymentError: 如果驱动未安装
        """
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise VLLMDeploymentError("nvidia-smi 命令失败")
            if "NVIDIA" not in result.stdout:
                raise VLLMDeploymentError("未检测到 NVIDIA GPU")
            return True
        except FileNotFoundError:
            raise VLLMDeploymentError("nvidia-smi 未找到，请安装 NVIDIA 驱动")
    
    def check_gpu_count(self, min_gpus: int = 1) -> int:
        """检查 GPU 数量
        
        Args:
            min_gpus: 最少需要的 GPU 数量
            
        Returns:
            检测到的 GPU 数量
            
        Raises:
            VLLMDeploymentError: 如果 GPU 数量不足
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise VLLMDeploymentError("查询 GPU 信息失败")
            
            gpu_count = len(result.stdout.strip().split("\n"))
            if gpu_count < min_gpus:
                raise VLLMDeploymentError(
                    f"检测到 {gpu_count} 个 GPU，至少需要 {min_gpus} 个"
                )
            return gpu_count
        except FileNotFoundError:
            raise VLLMDeploymentError("nvidia-smi 未找到")
    
    def install_vllm(self) -> bool:
        """安装 vLLM 包
        
        Returns:
            True 如果安装成功
            
        Raises:
            VLLMDeploymentError: 如果安装失败
        """
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "vllm"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                raise VLLMDeploymentError(
                    f"vLLM 安装失败: {result.stderr}"
                )
            return True
        except subprocess.TimeoutExpired:
            raise VLLMDeploymentError("vLLM 安装超时")
    
    def start_service(self) -> subprocess.Popen:
        """启动 vLLM 服务
        
        Returns:
            服务进程对象
            
        Raises:
            VLLMDeploymentError: 如果启动失败
        """
        try:
            args = ["python", "-m", "vllm.entrypoints.openai.api_server"]
            args.extend(self.config.to_args())
            
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return self.process
        except Exception as e:
            raise VLLMDeploymentError(f"启动 vLLM 服务失败: {e}")
    
    async def wait_for_service(self, timeout: int = 60) -> bool:
        """等待服务启动就绪
        
        Args:
            timeout: 最大等待时间（秒）
            
        Returns:
            True 如果服务就绪
            
        Raises:
            VLLMDeploymentError: 如果超时或服务启动失败
        """
        url = f"http://{self.config.host}:{self.config.port}/v1/models"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            
            await asyncio.sleep(1)
        
        raise VLLMDeploymentError(
            f"vLLM 服务未在 {timeout} 秒内启动"
        )
    
    async def verify_model_loaded(self) -> dict:
        """验证模型已加载
        
        Returns:
            模型信息字典
            
        Raises:
            VLLMDeploymentError: 如果模型未加载
        """
        url = f"http://{self.config.host}:{self.config.port}/v1/models"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        raise VLLMDeploymentError(f"查询模型失败: HTTP {resp.status}")
                    
                    data = await resp.json()
                    if not data.get("data"):
                        raise VLLMDeploymentError("未检测到已加载的模型")
                    
                    return data["data"][0]
        except aiohttp.ClientError as e:
            raise VLLMDeploymentError(f"连接 vLLM 服务失败: {e}")
    
    async def test_inference(self, prompt: str = "你好", max_tokens: int = 10) -> str:
        """测试推理功能
        
        Args:
            prompt: 输入提示词
            max_tokens: 最大生成 token 数
            
        Returns:
            生成的文本
            
        Raises:
            VLLMDeploymentError: 如果推理失败
        """
        url = f"http://{self.config.host}:{self.config.port}/v1/completions"
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        raise VLLMDeploymentError(f"推理请求失败: HTTP {resp.status}")
                    
                    data = await resp.json()
                    if not data.get("choices"):
                        raise VLLMDeploymentError("推理返回无效响应")
                    
                    return data["choices"][0].get("text", "")
        except aiohttp.ClientError as e:
            raise VLLMDeploymentError(f"推理请求失败: {e}")
    
    def stop_service(self) -> bool:
        """停止 vLLM 服务
        
        Returns:
            True 如果停止成功
        """
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            return True
        return False
    
    async def deploy(self) -> dict:
        """完整部署流程
        
        Returns:
            部署结果信息
            
        Raises:
            VLLMDeploymentError: 如果部署失败
        """
        try:
            # 1. 检查环境
            self.check_nvidia_driver()
            gpu_count = self.check_gpu_count(min_gpus=1)
            print(f"✓ 检测到 {gpu_count} 个 GPU")
            
            # 2. 安装 vLLM
            self.install_vllm()
            print("✓ vLLM 安装完成")
            
            # 3. 启动服务
            self.start_service()
            print("✓ vLLM 服务已启动")
            
            # 4. 等待服务就绪
            await self.wait_for_service()
            print("✓ vLLM 服务已就绪")
            
            # 5. 验证模型加载
            model_info = await self.verify_model_loaded()
            print(f"✓ 模型已加载: {model_info.get('id')}")
            
            # 6. 测试推理
            result = await self.test_inference()
            print(f"✓ 推理测试成功: {result[:50]}...")
            
            return {
                "status": "success",
                "gpu_count": gpu_count,
                "model": model_info.get("id"),
                "service_url": f"http://{self.config.host}:{self.config.port}",
            }
        except VLLMDeploymentError as e:
            self.stop_service()
            raise


async def main():
    """主函数"""
    deployer = VLLMDeployer()
    try:
        result = await deployer.deploy()
        print("\n部署成功!")
        print(f"服务地址: {result['service_url']}")
        print(f"模型: {result['model']}")
    except VLLMDeploymentError as e:
        print(f"\n部署失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
