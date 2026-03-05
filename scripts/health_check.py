"""
Sirus AI CRM — 各服务健康检查脚本

功能:
- 检查 Agent 引擎 (4090:8100) 健康状态
- 检查 CRM 后端 (mac_min_8T:8900) 健康状态
- 检查 Nginx 网关 (gateway:80) 可达性
- 检查 Git 服务器 (SSH:22) 可达性
- 检查 Redis (6379) 连通性
- 每 30 秒轮询一次，输出 JSON 格式结果

用法:
    python scripts/health_check.py                   # 持续轮询（每30s）
    python scripts/health_check.py --once             # 仅检查一次
    python scripts/health_check.py --interval 10      # 自定义轮询间隔（秒）

参考契约:
- contracts/health-api.yaml
- contracts/agent-api.yaml (HealthResponse)
- contracts/crm-api.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import enum
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

try:
    import aioredis
except ImportError:  # redis>=4.x 兼容
    import redis.asyncio as aioredis  # type: ignore[no-redef]

# ──────── 日志配置 ────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("health_check")

# ──────── 默认配置 ────────

DEFAULT_AGENT_HOST = "172.16.11.194"
DEFAULT_AGENT_PORT = 8100
DEFAULT_CRM_HOST = "172.16.12.50"
DEFAULT_CRM_PORT = 8900
DEFAULT_NGINX_HOST = "172.16.11.131"
DEFAULT_NGINX_PORT = 80
DEFAULT_GIT_HOST = "172.16.12.50"
DEFAULT_GIT_PORT = 22
DEFAULT_REDIS_HOST = "172.16.12.50"
DEFAULT_REDIS_PORT = 6379
DEFAULT_INTERVAL = 30
DEFAULT_TIMEOUT = 5.0


# ──────── 数据结构 ────────


class ServiceStatus(str, enum.Enum):
    """服务状态枚举，与 contracts/health-api.yaml 对齐。"""

    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class HealthCheckResult:
    """单个服务的健康检查结果。

    Attributes
    ----------
    service:
        服务名称，例如 ``agent_engine`` / ``crm_backend`` / ``nginx`` 等。
    status:
        服务状态：ok / degraded / error。
    timestamp:
        检查时刻 ISO-8601 字符串。
    details:
        附加详情字典（如子组件连通性）。
    latency_ms:
        检查耗时（毫秒）。
    """

    service: str
    status: ServiceStatus
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return {
            "service": self.service,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "details": self.details,
            "latency_ms": round(self.latency_ms, 2),
        }


# ──────── HealthChecker ────────


class HealthChecker:
    """异步健康检查器，聚合检查 5 个核心服务。

    Parameters
    ----------
    timeout:
        每个检查的 HTTP/TCP 超时秒数，默认 5.0。
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self.http_client: httpx.AsyncClient = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def close(self) -> None:
        """关闭内部 HTTP 客户端。"""
        await self.http_client.aclose()

    # ── 工具方法 ──

    @staticmethod
    def _now_iso() -> str:
        """返回当前 UTC 时间 ISO 字符串。"""
        return datetime.now(timezone.utc).isoformat()

    # ── Agent 引擎 ──

    async def check_agent_engine(
        self,
        host: str = DEFAULT_AGENT_HOST,
        port: int = DEFAULT_AGENT_PORT,
    ) -> HealthCheckResult:
        """检查 Agent 引擎健康状态。

        请求 ``GET /health`` 端点（参照 contracts/agent-api.yaml）。
        根据返回的 status / vllm / redis 字段判定服务状态。

        Returns
        -------
        HealthCheckResult
        """
        ts = self._now_iso()
        t0 = time.monotonic()
        try:
            resp = await self.http_client.get(f"http://{host}:{port}/health")
            latency = (time.monotonic() - t0) * 1000
            data = resp.json()

            # 判定状态
            api_status = data.get("status", "error")
            vllm = data.get("vllm", "unknown")
            redis_st = data.get("redis", "unknown")

            if api_status == "ok":
                status = ServiceStatus.OK
            elif api_status == "degraded":
                status = ServiceStatus.DEGRADED
            else:
                status = ServiceStatus.ERROR

            return HealthCheckResult(
                service="agent_engine",
                status=status,
                timestamp=ts,
                details={
                    "api": api_status,
                    "vllm": vllm,
                    "redis": redis_st,
                    "version": data.get("version"),
                },
                latency_ms=latency,
            )
        except httpx.TimeoutException as exc:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="agent_engine",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": "Request timeout"},
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="agent_engine",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": str(exc)},
                latency_ms=latency,
            )

    # ── CRM 后端 ──

    async def check_crm_backend(
        self,
        host: str = DEFAULT_CRM_HOST,
        port: int = DEFAULT_CRM_PORT,
    ) -> HealthCheckResult:
        """检查 CRM 后端健康状态。

        请求 ``GET /health`` 端点（参照 contracts/health-api.yaml）。

        Returns
        -------
        HealthCheckResult
        """
        ts = self._now_iso()
        t0 = time.monotonic()
        try:
            resp = await self.http_client.get(f"http://{host}:{port}/health")
            latency = (time.monotonic() - t0) * 1000
            data = resp.json()

            api_status = data.get("status", "error")
            db = data.get("db", "unknown")

            if api_status == "ok":
                status = ServiceStatus.OK
            elif api_status == "degraded":
                status = ServiceStatus.DEGRADED
            else:
                status = ServiceStatus.ERROR

            return HealthCheckResult(
                service="crm_backend",
                status=status,
                timestamp=ts,
                details={
                    "api": api_status,
                    "db": db,
                    "version": data.get("version"),
                },
                latency_ms=latency,
            )
        except httpx.TimeoutException:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="crm_backend",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": "Request timeout"},
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="crm_backend",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": str(exc)},
                latency_ms=latency,
            )

    # ── Nginx ──

    async def check_nginx(
        self,
        host: str = DEFAULT_NGINX_HOST,
        port: int = DEFAULT_NGINX_PORT,
    ) -> HealthCheckResult:
        """检查 Nginx 网关可达性。

        发起 ``GET /`` 请求，2xx/3xx 视为正常，5xx 视为降级。

        Returns
        -------
        HealthCheckResult
        """
        ts = self._now_iso()
        t0 = time.monotonic()
        try:
            resp = await self.http_client.get(f"http://{host}:{port}/")
            latency = (time.monotonic() - t0) * 1000

            if 200 <= resp.status_code < 400:
                status = ServiceStatus.OK
                details = {"http": "ok", "status_code": resp.status_code}
            elif resp.status_code >= 500:
                status = ServiceStatus.DEGRADED
                details = {
                    "http": f"status_{resp.status_code}",
                    "status_code": resp.status_code,
                }
            else:
                status = ServiceStatus.DEGRADED
                details = {
                    "http": f"status_{resp.status_code}",
                    "status_code": resp.status_code,
                }

            return HealthCheckResult(
                service="nginx",
                status=status,
                timestamp=ts,
                details=details,
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="nginx",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": str(exc)},
                latency_ms=latency,
            )

    # ── Git 服务器 (SSH) ──

    async def check_git_server(
        self,
        host: str = DEFAULT_GIT_HOST,
        port: int = DEFAULT_GIT_PORT,
    ) -> HealthCheckResult:
        """检查 Git 服务器 SSH 端口可达性。

        尝试 TCP 连接到 SSH 端口。

        Returns
        -------
        HealthCheckResult
        """
        ts = self._now_iso()
        t0 = time.monotonic()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.timeout,
            )
            latency = (time.monotonic() - t0) * 1000
            writer.close()
            await writer.wait_closed()

            return HealthCheckResult(
                service="git_server",
                status=ServiceStatus.OK,
                timestamp=ts,
                details={"ssh": "ok"},
                latency_ms=latency,
            )
        except asyncio.TimeoutError:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="git_server",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": "SSH connection timeout"},
                latency_ms=latency,
            )
        except ConnectionRefusedError:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="git_server",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": "Connection refused"},
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="git_server",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": str(exc)},
                latency_ms=latency,
            )

    # ── Redis ──

    async def check_redis(
        self,
        host: str = DEFAULT_REDIS_HOST,
        port: int = DEFAULT_REDIS_PORT,
    ) -> HealthCheckResult:
        """检查 Redis 连通性。

        使用 ``PING`` 命令验证。

        Returns
        -------
        HealthCheckResult
        """
        ts = self._now_iso()
        t0 = time.monotonic()
        try:
            r = await aioredis.from_url(
                f"redis://{host}:{port}",
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout,
            )
            try:
                pong = await r.ping()
                latency = (time.monotonic() - t0) * 1000

                if pong:
                    return HealthCheckResult(
                        service="redis",
                        status=ServiceStatus.OK,
                        timestamp=ts,
                        details={"ping": "ok"},
                        latency_ms=latency,
                    )
                else:
                    return HealthCheckResult(
                        service="redis",
                        status=ServiceStatus.ERROR,
                        timestamp=ts,
                        details={"error": "PING failed"},
                        latency_ms=latency,
                    )
            finally:
                await r.close()
        except ConnectionRefusedError:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": "Connection refused"},
                latency_ms=latency,
            )
        except Exception as exc:
            latency = (time.monotonic() - t0) * 1000
            return HealthCheckResult(
                service="redis",
                status=ServiceStatus.ERROR,
                timestamp=ts,
                details={"error": str(exc)},
                latency_ms=latency,
            )

    # ── 批量检查 ──

    async def check_all(
        self,
        *,
        agent_host: str = DEFAULT_AGENT_HOST,
        agent_port: int = DEFAULT_AGENT_PORT,
        crm_host: str = DEFAULT_CRM_HOST,
        crm_port: int = DEFAULT_CRM_PORT,
        nginx_host: str = DEFAULT_NGINX_HOST,
        nginx_port: int = DEFAULT_NGINX_PORT,
        git_host: str = DEFAULT_GIT_HOST,
        git_port: int = DEFAULT_GIT_PORT,
        redis_host: str = DEFAULT_REDIS_HOST,
        redis_port: int = DEFAULT_REDIS_PORT,
    ) -> Dict[str, HealthCheckResult]:
        """并发检查所有 5 个核心服务。

        Returns
        -------
        Dict[str, HealthCheckResult]
            key 为 service 名称。
        """
        tasks = [
            self.check_agent_engine(host=agent_host, port=agent_port),
            self.check_crm_backend(host=crm_host, port=crm_port),
            self.check_nginx(host=nginx_host, port=nginx_port),
            self.check_git_server(host=git_host, port=git_port),
            self.check_redis(host=redis_host, port=redis_port),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return {r.service: r for r in results}


# ──────── 输出格式化 ────────

# ANSI 颜色代码
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_RESET = "\033[0m"

_STATUS_COLORS = {
    ServiceStatus.OK: _GREEN,
    ServiceStatus.DEGRADED: _YELLOW,
    ServiceStatus.ERROR: _RED,
}

_STATUS_ICONS = {
    ServiceStatus.OK: "✅",
    ServiceStatus.DEGRADED: "⚠️",
    ServiceStatus.ERROR: "❌",
}


def print_results(results: Dict[str, HealthCheckResult]) -> None:
    """将结果打印为人类可读的彩色表格。"""
    print(f"\n{'─' * 70}")
    print(f"  健康检查报告  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'─' * 70}")
    for name, result in results.items():
        icon = _STATUS_ICONS.get(result.status, "?")
        color = _STATUS_COLORS.get(result.status, _RESET)
        status_str = f"{color}{result.status.value.upper():>8s}{_RESET}"
        latency_str = f"{result.latency_ms:>8.1f}ms"
        detail_str = json.dumps(result.details, ensure_ascii=False)
        print(f"  {icon} {name:<16s} {status_str}  {latency_str}  {detail_str}")
    print(f"{'─' * 70}\n")


def print_results_json(results: Dict[str, HealthCheckResult]) -> None:
    """将结果输出为 JSON 格式（便于机器解析）。"""
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {name: r.to_dict() for name, r in results.items()},
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ──────── 主程序 ────────


async def run_loop(
    interval: int = DEFAULT_INTERVAL,
    once: bool = False,
    json_output: bool = False,
) -> None:
    """主轮询循环。

    Parameters
    ----------
    interval:
        轮询间隔秒数。
    once:
        为 True 时只检查一次即退出。
    json_output:
        为 True 时输出 JSON 格式。
    """
    checker = HealthChecker()
    stop_event = asyncio.Event()

    # 优雅退出
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows 不支持 add_signal_handler
            pass

    logger.info(
        "健康检查启动 (间隔=%ds, 单次=%s, JSON=%s)",
        interval,
        once,
        json_output,
    )

    try:
        while not stop_event.is_set():
            results = await checker.check_all()

            if json_output:
                print_results_json(results)
            else:
                print_results(results)

            if once:
                break

            # 等待 interval 秒或收到停止信号
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass  # 正常超时，继续下一轮
    finally:
        await checker.close()
        logger.info("健康检查已停止")


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        description="Sirus AI CRM 服务健康检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL,
        help=f"轮询间隔秒数 (默认 {DEFAULT_INTERVAL})",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅检查一次后退出",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 JSON 格式",
    )

    args = parser.parse_args()
    asyncio.run(run_loop(interval=args.interval, once=args.once, json_output=args.json_output))


if __name__ == "__main__":
    main()
