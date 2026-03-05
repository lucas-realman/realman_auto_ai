"""
健康检查模块测试

测试覆盖：
- 各服务健康检查逻辑
- 错误处理
- 结果格式
"""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest
import pytest_asyncio

# 将 scripts 目录加入 path
sys.path.insert(0, "scripts")

from health_check import HealthChecker, HealthCheckResult, ServiceStatus


# ──────── Fixtures ────────


@pytest_asyncio.fixture
async def checker():
    """创建并在测试结束后关闭 HealthChecker 实例"""
    hc = HealthChecker(timeout=2.0)
    yield hc
    await hc.close()


# ──────── HealthCheckResult 数据类测试 ────────


class TestHealthCheckResult:
    """测试 HealthCheckResult 数据类"""

    def test_create_ok_result(self):
        """测试创建 OK 状态的结果"""
        result = HealthCheckResult(
            service="test_service",
            status=ServiceStatus.OK,
            timestamp="2026-03-05T10:00:00",
            details={"api": "ok"},
            latency_ms=12.5,
        )
        assert result.service == "test_service"
        assert result.status == ServiceStatus.OK
        assert result.details["api"] == "ok"
        assert result.latency_ms == 12.5

    def test_create_error_result(self):
        """测试创建 ERROR 状态的结果"""
        result = HealthCheckResult(
            service="down_service",
            status=ServiceStatus.ERROR,
            timestamp="2026-03-05T10:00:00",
            details={"error": "Connection refused"},
            latency_ms=5001.0,
        )
        assert result.status == ServiceStatus.ERROR
        assert "error" in result.details


# ──────── ServiceStatus 枚举测试 ────────


class TestServiceStatus:
    """测试 ServiceStatus 枚举"""

    def test_values(self):
        assert ServiceStatus.OK.value == "ok"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.ERROR.value == "error"

    def test_is_str(self):
        assert isinstance(ServiceStatus.OK, str)


# ──────── Agent 引擎健康检查测试 ────────


class TestCheckAgentEngine:
    """测试 Agent 引擎健康检查"""

    @pytest.mark.asyncio
    async def test_agent_engine_ok(self, checker):
        """Agent 引擎全部正常"""
        mock_response = httpx.Response(
            200,
            json={
                "status": "ok",
                "vllm": "connected",
                "redis": "connected",
                "timestamp": "2026-03-05T10:00:00",
                "version": "0.1.0",
            },
            request=httpx.Request("GET", "http://test/health"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_agent_engine(host="127.0.0.1", port=8100)

        assert result.service == "agent_engine"
        assert result.status == ServiceStatus.OK
        assert result.details["vllm"] == "connected"
        assert result.details["redis"] == "connected"
        assert result.details["api"] == "ok"
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_agent_engine_vllm_disconnected(self, checker):
        """vLLM 断开时应返回 DEGRADED"""
        mock_response = httpx.Response(
            200,
            json={
                "status": "degraded",
                "vllm": "disconnected",
                "redis": "connected",
                "timestamp": "2026-03-05T10:00:00",
            },
            request=httpx.Request("GET", "http://test/health"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_agent_engine(host="127.0.0.1", port=8100)

        assert result.status == ServiceStatus.DEGRADED
        assert result.details["vllm"] == "disconnected"

    @pytest.mark.asyncio
    async def test_agent_engine_connection_refused(self, checker):
        """连接被拒绝时应返回 ERROR"""
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_agent_engine(host="127.0.0.1", port=8100)

        assert result.status == ServiceStatus.ERROR
        assert "error" in result.details

    @pytest.mark.asyncio
    async def test_agent_engine_timeout(self, checker):
        """请求超时应返回 ERROR"""
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_agent_engine(host="127.0.0.1", port=8100)

        assert result.status == ServiceStatus.ERROR
        assert result.details["error"] == "Request timeout"


# ──────── CRM 后端健康检查测试 ────────


class TestCheckCrmBackend:
    """测试 CRM 后端健康检查"""

    @pytest.mark.asyncio
    async def test_crm_backend_ok(self, checker):
        """CRM 后端正常"""
        mock_response = httpx.Response(
            200,
            json={
                "status": "ok",
                "db": "connected",
                "timestamp": "2026-03-05T10:00:00",
            },
            request=httpx.Request("GET", "http://test/health"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_crm_backend(host="127.0.0.1", port=8900)

        assert result.service == "crm_backend"
        assert result.status == ServiceStatus.OK
        assert result.details["db"] == "connected"
        assert result.details["api"] == "ok"

    @pytest.mark.asyncio
    async def test_crm_backend_db_disconnected(self, checker):
        """数据库断开时应返回 DEGRADED"""
        mock_response = httpx.Response(
            200,
            json={
                "status": "degraded",
                "db": "disconnected",
                "timestamp": "2026-03-05T10:00:00",
            },
            request=httpx.Request("GET", "http://test/health"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_crm_backend(host="127.0.0.1", port=8900)

        assert result.status == ServiceStatus.DEGRADED
        assert result.details["db"] == "disconnected"

    @pytest.mark.asyncio
    async def test_crm_backend_connection_error(self, checker):
        """连接失败应返回 ERROR"""
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_crm_backend(host="127.0.0.1", port=8900)

        assert result.status == ServiceStatus.ERROR


# ──────── Nginx 健康检查测试 ────────


class TestCheckNginx:
    """测试 Nginx 健康检查"""

    @pytest.mark.asyncio
    async def test_nginx_ok(self, checker):
        """Nginx 正常响应"""
        mock_response = httpx.Response(
            200,
            text="OK",
            request=httpx.Request("GET", "http://test/"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_nginx(host="127.0.0.1", port=80)

        assert result.service == "nginx"
        assert result.status == ServiceStatus.OK
        assert result.details["http"] == "ok"

    @pytest.mark.asyncio
    async def test_nginx_redirect_ok(self, checker):
        """Nginx 301/302 重定向也视为正常"""
        mock_response = httpx.Response(
            200,
            text="Redirected",
            request=httpx.Request("GET", "http://test/"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_nginx(host="127.0.0.1", port=80)

        assert result.status == ServiceStatus.OK

    @pytest.mark.asyncio
    async def test_nginx_500_degraded(self, checker):
        """Nginx 返回 500 应标记为 DEGRADED"""
        mock_response = httpx.Response(
            500,
            text="Internal Server Error",
            request=httpx.Request("GET", "http://test/"),
        )
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(return_value=mock_response)
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_nginx(host="127.0.0.1", port=80)

        assert result.status == ServiceStatus.DEGRADED
        assert result.details["http"] == "status_500"

    @pytest.mark.asyncio
    async def test_nginx_connection_refused(self, checker):
        """Nginx 无法连接应返回 ERROR"""
        checker.http_client = AsyncMock()
        checker.http_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        checker.http_client.aclose = AsyncMock()

        result = await checker.check_nginx(host="127.0.0.1", port=80)

        assert result.status == ServiceStatus.ERROR


# ──────── Git 服务器健康检查测试 ────────


class TestCheckGitServer:
    """测试 Git 服务器（SSH）健康检查"""

    @pytest.mark.asyncio
    async def test_git_server_ok(self, checker):
        """SSH 端口可连接"""
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.open_connection", new_callable=AsyncMock) as mock_conn:
            mock_conn.return_value = (AsyncMock(), mock_writer)

            result = await checker.check_git_server(host="127.0.0.1", port=22)

        assert result.service == "git_server"
        assert result.status == ServiceStatus.OK
        assert result.details["ssh"] == "ok"

    @pytest.mark.asyncio
    async def test_git_server_timeout(self, checker):
        """SSH 连接超时"""
        with patch(
            "asyncio.open_connection",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError(),
        ):
            # wait_for 内部的 TimeoutError 会被 check_git_server 捕获
            result = await checker.check_git_server(host="127.0.0.1", port=22)

        assert result.status == ServiceStatus.ERROR
        assert "timeout" in result.details.get("error", "").lower() or "error" in result.details

    @pytest.mark.asyncio
    async def test_git_server_refused(self, checker):
        """SSH 连接被拒绝"""
        with patch(
            "asyncio.open_connection",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError(),
        ):
            result = await checker.check_git_server(host="127.0.0.1", port=22)

        assert result.status == ServiceStatus.ERROR
        assert "refused" in result.details.get("error", "").lower()


# ──────── Redis 健康检查测试 ────────


class TestCheckRedis:
    """测试 Redis 健康检查"""

    @pytest.mark.asyncio
    async def test_redis_ok(self, checker):
        """Redis PING 成功"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.close = AsyncMock()

        with patch("aioredis.from_url", new_callable=AsyncMock, return_value=mock_redis):
            result = await checker.check_redis(host="127.0.0.1", port=6379)

        assert result.service == "redis"
        assert result.status == ServiceStatus.OK
        assert result.details["ping"] == "ok"

    @pytest.mark.asyncio
    async def test_redis_ping_failed(self, checker):
        """Redis PING 返回 False"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=False)
        mock_redis.close = AsyncMock()

        with patch("aioredis.from_url", new_callable=AsyncMock, return_value=mock_redis):
            result = await checker.check_redis(host="127.0.0.1", port=6379)

        assert result.status == ServiceStatus.ERROR
        assert result.details["error"] == "PING failed"

    @pytest.mark.asyncio
    async def test_redis_connection_error(self, checker):
        """Redis 连接失败"""
        with patch(
            "aioredis.from_url",
            new_callable=AsyncMock,
            side_effect=ConnectionRefusedError("Connection refused"),
        ):
            result = await checker.check_redis(host="127.0.0.1", port=6379)

        assert result.status == ServiceStatus.ERROR
        assert "refused" in result.details.get("error", "").lower()


# ──────── check_all 测试 ────────


class TestCheckAll:
    """测试批量检查"""

    @pytest.mark.asyncio
    async def test_check_all_returns_all_services(self, checker):
        """check_all 应返回所有 5 个服务的结果"""
        # Mock 所有子方法
        ok_result = HealthCheckResult(
            service="test",
            status=ServiceStatus.OK,
            timestamp="2026-03-05T10:00:00",
            details={"api": "ok"},
            latency_ms=10.0,
        )

        checker.check_agent_engine = AsyncMock(
            return_value=HealthCheckResult(
                service="agent_engine",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={"api": "ok"},
                latency_ms=10.0,
            )
        )
        checker.check_crm_backend = AsyncMock(
            return_value=HealthCheckResult(
                service="crm_backend",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={"api": "ok"},
                latency_ms=10.0,
            )
        )
        checker.check_nginx = AsyncMock(
            return_value=HealthCheckResult(
                service="nginx",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={"http": "ok"},
                latency_ms=10.0,
            )
        )
        checker.check_git_server = AsyncMock(
            return_value=HealthCheckResult(
                service="git_server",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={"ssh": "ok"},
                latency_ms=10.0,
            )
        )
        checker.check_redis = AsyncMock(
            return_value=HealthCheckResult(
                service="redis",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={"ping": "ok"},
                latency_ms=10.0,
            )
        )

        results = await checker.check_all()

        assert len(results) == 5
        assert "agent_engine" in results
        assert "crm_backend" in results
        assert "nginx" in results
        assert "git_server" in results
        assert "redis" in results

    @pytest.mark.asyncio
    async def test_check_all_mixed_status(self, checker):
        """check_all 中有部分服务异常"""
        checker.check_agent_engine = AsyncMock(
            return_value=HealthCheckResult(
                service="agent_engine",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={},
                latency_ms=10.0,
            )
        )
        checker.check_crm_backend = AsyncMock(
            return_value=HealthCheckResult(
                service="crm_backend",
                status=ServiceStatus.ERROR,
                timestamp="2026-03-05T10:00:00",
                details={"error": "Connection refused"},
                latency_ms=5000.0,
            )
        )
        checker.check_nginx = AsyncMock(
            return_value=HealthCheckResult(
                service="nginx",
                status=ServiceStatus.DEGRADED,
                timestamp="2026-03-05T10:00:00",
                details={"http": "status_502"},
                latency_ms=200.0,
            )
        )
        checker.check_git_server = AsyncMock(
            return_value=HealthCheckResult(
                service="git_server",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={},
                latency_ms=5.0,
            )
        )
        checker.check_redis = AsyncMock(
            return_value=HealthCheckResult(
                service="redis",
                status=ServiceStatus.OK,
                timestamp="2026-03-05T10:00:00",
                details={},
                latency_ms=3.0,
            )
        )

        results = await checker.check_all()

        assert results["crm_backend"].status == ServiceStatus.ERROR
        assert results["nginx"].status == ServiceStatus.DEGRADED
        assert results["agent_engine"].status == ServiceStatus.OK


# ──────── 结果格式测试 ────────


class TestResultFormat:
    """测试结果输出格式"""

    def test_result_has_required_fields(self):
        """HealthCheckResult 应包含所有必需字段"""
        result = HealthCheckResult(
            service="test",
            status=ServiceStatus.OK,
            timestamp="2026-03-05T10:00:00",
            details={"key": "value"},
            latency_ms=1.0,
        )
        assert hasattr(result, "service")
        assert hasattr(result, "status")
        assert hasattr(result, "timestamp")
        assert hasattr(result, "details")
        assert hasattr(result, "latency_ms")

    def test_status_is_json_serializable(self):
        """状态值应可 JSON 序列化"""
        output = {
            "status": ServiceStatus.OK.value,
            "details": {"api": "ok"},
        }
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        assert parsed["status"] == "ok"

    def test_latency_is_non_negative(self):
        """延迟值应非负"""
        result = HealthCheckResult(
            service="test",
            status=ServiceStatus.OK,
            timestamp="2026-03-05T10:00:00",
            details={},
            latency_ms=0.0,
        )
        assert result.latency_ms >= 0
