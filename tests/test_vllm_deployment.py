"""vLLM 部署验证测试"""
import subprocess
import time
import requests
import pytest


def test_nvidia_driver_installed():
    """验证 NVIDIA 驱动已安装"""
    result = subprocess.run(
        ["nvidia-smi"], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, "nvidia-smi 命令失败"
    assert "NVIDIA" in result.stdout, "未检测到 NVIDIA GPU"


def test_gpu_count():
    """验证至少有 1 个 GPU（理想 2 个）"""
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    gpu_count = len(result.stdout.strip().split("\n"))
    assert gpu_count >= 1, f"检测到 {gpu_count} 个 GPU，至少需要 1 个"


@pytest.mark.acceptance
def test_vllm_service_health():
    """验证 vLLM 服务健康（需要服务已启动）"""
    url = "http://localhost:8000/v1/models"
    
    # 等待服务启动（最多 30 秒）
    for _ in range(30):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                break
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    else:
        pytest.fail("vLLM 服务未在 30 秒内启动")
    
    # 验证返回模型列表
    response = requests.get(url, timeout=5)
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) > 0
    assert "id" in data["data"][0]
    print(f"检测到模型: {data['data'][0]['id']}")


@pytest.mark.acceptance
def test_vllm_inference():
    """验证 vLLM 推理功能（需要服务已启动）"""
    url = "http://localhost:8000/v1/completions"
    payload = {
        "model": "Qwen/Qwen3-30B-A3B",
        "prompt": "你好",
        "max_tokens": 10,
        "temperature": 0.7,
    }
    
    response = requests.post(url, json=payload, timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "text" in data["choices"][0]
    print(f"推理结果: {data['choices'][0]['text']}")
