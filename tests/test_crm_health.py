"""
Sirus AI-CRM 测试 — CRM 服务健康检查
验证 CRM API 可达且基本功能正常。
"""
from __future__ import annotations

import os
import pytest

# CRM 地址, 可通过环境变量覆盖
CRM_BASE = os.getenv("CRM_BASE_URL", "http://172.16.12.50:8900")

# 标记: 需要网络访问, 默认跳过 (CI 或手动指定时运行)
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1",
    reason="需要设置 RUN_INTEGRATION=1 启用集成测试",
)


@pytest.fixture
def http_client():
    """同步 httpx 客户端"""
    import httpx
    with httpx.Client(base_url=CRM_BASE, timeout=10) as client:
        yield client


class TestCrmHealth:
    """CRM API 健康检查"""

    def test_health_endpoint(self, http_client):
        resp = http_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok" or "status" in data

    def test_docs_accessible(self, http_client):
        """Swagger UI 可访问"""
        resp = http_client.get("/docs")
        assert resp.status_code == 200

    def test_customers_list(self, http_client):
        """客户列表接口可调用"""
        resp = http_client.get("/api/v1/customers")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (list, dict))

    def test_activities_list(self, http_client):
        """活动列表接口可调用"""
        resp = http_client.get("/api/v1/activities")
        assert resp.status_code == 200

    def test_deals_list(self, http_client):
        """商机列表接口可调用"""
        resp = http_client.get("/api/v1/deals")
        assert resp.status_code == 200
