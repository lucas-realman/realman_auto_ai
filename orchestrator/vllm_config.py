"""vLLM 配置管理"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class VLLMConfig:
    """vLLM 服务配置"""
    
    # 服务地址
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 模型配置
    model_name: str = "Qwen/Qwen3-30B-A3B"
    
    # GPU 配置
    tensor_parallel_size: int = 2  # 2×4090 张量并行
    gpu_memory_utilization: float = 0.85
    
    # 推理配置
    max_model_len: Optional[int] = None  # 自动推断
    max_num_seqs: int = 256
    enable_prefix_caching: bool = True
    
    # 性能配置
    dtype: str = "auto"
    seed: int = 0
    
    def to_args(self) -> list[str]:
        """转换为 vLLM 命令行参数"""
        args = [
            "--model", self.model_name,
            "--host", self.host,
            "--port", str(self.port),
            "--tensor-parallel-size", str(self.tensor_parallel_size),
            "--gpu-memory-utilization", str(self.gpu_memory_utilization),
            "--max-num-seqs", str(self.max_num_seqs),
            "--dtype", self.dtype,
            "--seed", str(self.seed),
        ]
        
        if self.enable_prefix_caching:
            args.append("--enable-prefix-caching")
        
        if self.max_model_len:
            args.extend(["--max-model-len", str(self.max_model_len)])
        
        return args
