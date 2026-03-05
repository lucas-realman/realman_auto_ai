"""
Sirus AI-CRM 验收测试 — 公共 fixtures
测试项目实际产出物是否符合任务卡「完成标志」。

运行方式: RUN_ACCEPTANCE=1 pytest tests/acceptance/ -v
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

# ── 机器 IP 映射 (与 config.yaml 一致) ──

MACHINE_HOSTS = {
    "W0": "172.16.14.201",   # orchestrator
    "W1": "172.16.11.194",   # 4090
    "W2": "172.16.12.50",    # mac_min_8T
    "W3": "172.16.14.215",   # gateway
    "W4": "172.16.14.90",    # data_center
}

# 机器名 → config名 映射
MACHINE_NAMES = {
    "W0": "orchestrator",
    "W1": "4090",
    "W2": "mac_min_8T",
    "W3": "gateway",
    "W4": "data_center",
}

# SSH 用户
SSH_USERS = {
    "W0": "realman",
    "W1": "user",
    "W2": "edge_sale",
    "W3": "realman",
    "W4": "realman",
}

# 已知服务端点
SERVICE_ENDPOINTS = {
    "vllm":         {"host": MACHINE_HOSTS["W1"], "port": 8000, "health": "/v1/models"},
    "crm":          {"host": MACHINE_HOSTS["W2"], "port": 8900, "health": "/health"},
    "agent":        {"host": MACHINE_HOSTS["W1"], "port": 8100, "health": "/health"},
    "dashboard":    {"host": MACHINE_HOSTS["W1"], "port": 3000, "health": "/"},
    "dingtalk_bot": {"host": MACHINE_HOSTS["W3"], "port": 9000, "health": "/health"},
}


# ── 门控: 需要 RUN_ACCEPTANCE=1 才运行 ──

def _skip_unless_acceptance():
    if os.environ.get("RUN_ACCEPTANCE") != "1":
        pytest.skip("跳过验收测试 (设置 RUN_ACCEPTANCE=1 启用)")


@pytest.fixture(autouse=True)
def acceptance_gate():
    """所有验收测试的准入门控"""
    _skip_unless_acceptance()


# ── 公共 fixtures ──

@pytest.fixture
def machines():
    return MACHINE_HOSTS


@pytest.fixture
def services():
    return SERVICE_ENDPOINTS


# ── 工具函数 ──

def ssh_check(
    machine: str,
    command: str,
    timeout: int = 30,
) -> subprocess.CompletedProcess:
    """在远程机器上执行命令并返回结果"""
    host = MACHINE_HOSTS[machine]
    user = SSH_USERS[machine]
    result = subprocess.run(
        [
            "ssh",
            "-o", "ConnectTimeout=5",
            "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result


def http_get(
    host: str,
    port: int,
    path: str = "/",
    timeout: int = 10,
) -> "httpx.Response":
    """HTTP GET 请求"""
    assert httpx is not None, "需要安装 httpx: pip install httpx"
    url = f"http://{host}:{port}{path}"
    return httpx.get(url, timeout=timeout, follow_redirects=True)


def http_post(
    host: str,
    port: int,
    path: str,
    json_body: Optional[dict] = None,
    timeout: int = 30,
) -> "httpx.Response":
    """HTTP POST 请求"""
    assert httpx is not None, "需要安装 httpx: pip install httpx"
    url = f"http://{host}:{port}{path}"
    return httpx.post(url, json=json_body, timeout=timeout, follow_redirects=True)
