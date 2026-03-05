"""CRM 后端健康检查测试。

验收标准: uvicorn crm.main:app 启动，/health 返回 200。

测试使用 httpx ASGITransport 直接调用 FastAPI app，
无需真实数据库连接即可验证路由和响应格式。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from crm.main import app


@pytest.fixture
async def client():
    """创建异步测试客户端（基于 ASGI Transport，无需启动服务器）。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


class TestHealthEndpoint:
    """GET /health 端点测试组。"""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient):
        """GET /health 应返回 200 状态码。"""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_response_has_status(self, client: AsyncClient):
        """返回体应包含 status 字段，值为 ok / degraded / error。"""
        response = await client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] in ("ok", "degraded", "error")

    @pytest.mark.asyncio
    async def test_health_response_has_timestamp(self, client: AsyncClient):
        """返回体应包含 timestamp 字段（ISO-8601 格式）。"""
        response = await client.get("/health")
        data = response.json()
        assert "timestamp" in data
        assert isinstance(data["timestamp"], str)
        assert len(data["timestamp"]) > 10  # ISO-8601 至少有日期部分

    @pytest.mark.asyncio
    async def test_health_response_has_version(self, client: AsyncClient):
        """返回体应包含 version 字段。"""
        response = await client.get("/health")
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    @pytest.mark.asyncio
    async def test_health_response_has_db_field(self, client: AsyncClient):
        """返回体应包含 db 字段（connected / disconnected）。"""
        response = await client.get("/health")
        data = response.json()
        assert "db" in data
        assert data["db"] in ("connected", "disconnected")


class TestOpenAPIDocs:
    """OpenAPI 文档可访问性测试。"""

    @pytest.mark.asyncio
    async def test_docs_accessible(self, client: AsyncClient):
        """Swagger UI /docs 应返回 200。"""
        response = await client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_redoc_accessible(self, client: AsyncClient):
        """ReDoc /redoc 应返回 200。"""
        response = await client.get("/redoc")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_openapi_json_valid(self, client: AsyncClient):
        """/openapi.json 应返回有效的 OpenAPI 规范。"""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["info"]["title"] == "Sirus AI-CRM"
        assert data["info"]["version"] == "0.1.0"
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_openapi_has_health_path(self, client: AsyncClient):
        """/openapi.json 应包含 /health 路径定义。"""
        response = await client.get("/openapi.json")
        data = response.json()
        assert "/health" in data["paths"]
