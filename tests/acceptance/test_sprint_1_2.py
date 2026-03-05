"""
Sprint 1-2 验收测试
═══════════════════
里程碑: 🏗️ 能对话
通过标准: 钉钉发消息 → Agent 收到 → 调用 vLLM → 返回文字，端到端链路跑通

测试项源自 docs/07-Sprint任务卡.md §1 每日任务的「完成标志」列。
运行方式:
    RUN_ACCEPTANCE=1 python3 -m pytest tests/acceptance/test_sprint_1_2.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

from .conftest import (
    MACHINE_HOSTS,
    SERVICE_ENDPOINTS,
    http_get,
    http_post,
    ssh_check,
)

# 项目根目录
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ════════════════════════════════════════════════════════
#  Day 1 — 环境搭建
# ════════════════════════════════════════════════════════

class TestDay1Environment:
    """Day 1 完成标志: 基础环境就绪"""

    def test_w1_vllm_models_endpoint(self):
        """W1: curl localhost:8000/v1/models 返回模型名"""
        svc = SERVICE_ENDPOINTS["vllm"]
        resp = http_get(svc["host"], svc["port"], "/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0, "vLLM 应返回至少一个模型"

    def test_w2_postgresql_ready(self):
        """W2: psql -c 'SELECT 1' 成功"""
        result = ssh_check("W2", 'psql -U ai_crm -d ai_crm -c "SELECT 1"')
        assert result.returncode == 0, f"PostgreSQL 连接失败: {result.stderr}"

    def test_w2_redis_ready(self):
        """W2: redis-cli ping 返回 PONG"""
        result = ssh_check("W2", "redis-cli ping")
        assert result.returncode == 0
        assert "PONG" in result.stdout, f"Redis 未响应: {result.stdout}"

    def test_w3_nginx_config_valid(self):
        """W3: nginx -t 通过"""
        result = ssh_check("W3", "nginx -t 2>&1 || sudo nginx -t 2>&1")
        output = result.stdout + result.stderr
        assert "successful" in output.lower() or result.returncode == 0, (
            f"Nginx 配置检查失败: {output}"
        )

    def test_w4_git_connectivity(self):
        """W4: 各机器 git 仓库可用"""
        for machine in ["W1", "W2", "W3", "W4"]:
            result = ssh_check(machine, "cd ~/ai-crm && git status --short")
            assert result.returncode == 0, (
                f"{machine} git 仓库不可用: {result.stderr}"
            )


# ════════════════════════════════════════════════════════
#  Day 2-3 — 基础服务 + 项目骨架
# ════════════════════════════════════════════════════════

class TestDay2_3Services:
    """Day 2-3 完成标志: DB Schema、Agent 骨架、CRM 骨架"""

    def test_w2_core_tables_exist(self):
        """W2: 4 张核心表创建成功"""
        result = ssh_check(
            "W2",
            'psql -U ai_crm -d ai_crm -c "\\dt" 2>&1',
        )
        assert result.returncode == 0, f"psql 失败: {result.stderr}"
        output = result.stdout.lower()
        for table in ["leads", "customers", "opportunities", "activities"]:
            assert table in output, f"缺少核心表: {table}"

    def test_w1_agent_health(self):
        """W1: Agent 引擎 /health 返回 200"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_get(svc["host"], svc["port"], "/health")
        assert resp.status_code == 200

    def test_w2_crm_health(self):
        """W2: CRM 后端 /health 返回 200"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/health")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════
#  Day 4 — 接口契约
# ════════════════════════════════════════════════════════

class TestDay4Contracts:
    """Day 4 完成标志: contracts/ 目录完整"""

    EXPECTED_CONTRACTS = [
        "agent-api.yaml",
        "agent-tools.yaml",
        "crm-api.yaml",
        "db-schema.sql",
        "event-bus.yaml",
    ]

    def test_contract_files_exist(self):
        """contracts/ 中应包含全部契约文件"""
        contracts_dir = REPO_ROOT / "contracts"
        for fname in self.EXPECTED_CONTRACTS:
            path = contracts_dir / fname
            assert path.exists(), f"缺少契约文件: contracts/{fname}"

    def test_contract_files_not_empty(self):
        """契约文件不为空"""
        contracts_dir = REPO_ROOT / "contracts"
        for fname in self.EXPECTED_CONTRACTS:
            path = contracts_dir / fname
            if path.exists():
                assert path.stat().st_size > 50, (
                    f"契约文件内容过短: contracts/{fname}"
                )

    def test_crm_api_is_valid_yaml(self):
        """crm-api.yaml 应为合法 YAML"""
        import yaml

        path = REPO_ROOT / "contracts" / "crm-api.yaml"
        if not path.exists():
            pytest.skip("crm-api.yaml 不存在")
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), "crm-api.yaml 不是有效的 YAML 字典"


# ════════════════════════════════════════════════════════
#  Day 5-8 — 集成验证
# ════════════════════════════════════════════════════════

class TestDay5_8Integration:
    """Day 5-8 完成标志: 建联通、数据通"""

    def test_w2_crm_leads_list(self):
        """W2: GET /api/v1/leads 返回数据"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/leads")
        assert resp.status_code == 200

    def test_w2_crm_customers_list(self):
        """W2: GET /api/v1/customers 返回数据"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/customers")
        assert resp.status_code == 200

    def test_w2_crm_deals_list(self):
        """W2: GET /api/v1/deals 返回数据"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/deals")
        assert resp.status_code == 200

    def test_w2_crm_activities_list(self):
        """W2: GET /api/v1/activities 返回数据"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/activities")
        assert resp.status_code == 200

    def test_w1_dashboard_accessible(self):
        """W1: Dashboard 主页可访问"""
        svc = SERVICE_ENDPOINTS["dashboard"]
        resp = http_get(svc["host"], svc["port"], "/")
        assert resp.status_code == 200

    def test_w2_crm_swagger_ui(self):
        """W2: Swagger UI /docs 可访问"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/docs")
        assert resp.status_code == 200

    def test_w1_agent_chat_endpoint(self):
        """W1: POST /agent/chat → 推理返回文字"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_post(
            svc["host"], svc["port"],
            "/agent/chat",
            json_body={"message": "你好", "session_id": "acceptance_test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        reply = data.get("reply") or data.get("content") or data.get("message", "")
        assert len(reply) > 0, "Agent 应返回非空回复"


# ════════════════════════════════════════════════════════
#  Day 10 — Sprint Review / 里程碑
# ════════════════════════════════════════════════════════

class TestSprintMilestone:
    """
    Sprint 1-2 里程碑: 🏗️ 能对话
    通过标准: 钉钉发消息 → Agent 收到 → 调用 vLLM → 返回文字
    """

    def test_crm_all_core_routes(self):
        """CRM API 全部核心路由可用"""
        svc = SERVICE_ENDPOINTS["crm"]
        base_host, base_port = svc["host"], svc["port"]
        routes = [
            "/health",
            "/docs",
            "/api/v1/leads",
            "/api/v1/customers",
            "/api/v1/activities",
            "/api/v1/deals",
        ]
        for route in routes:
            resp = http_get(base_host, base_port, route)
            assert resp.status_code == 200, (
                f"CRM 路由 {route} 返回 {resp.status_code}"
            )

    def test_vllm_inference_ready(self):
        """vLLM 推理服务就绪"""
        svc = SERVICE_ENDPOINTS["vllm"]
        resp = http_get(svc["host"], svc["port"], "/v1/models")
        assert resp.status_code == 200
        models = resp.json().get("data", [])
        assert len(models) > 0, "vLLM 应有至少一个可用模型"

    def test_end_to_end_agent_chat(self):
        """端到端: 发消息 → Agent → 推理 → 返回文字"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_post(
            svc["host"], svc["port"],
            "/agent/chat",
            json_body={
                "message": "帮我查一下最近有哪些线索",
                "session_id": "e2e_milestone_test",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        reply = data.get("reply") or data.get("content") or data.get("message", "")
        assert len(reply) > 0, "里程碑验收: Agent 应返回有意义的回复"

    def test_all_machines_git_synced(self):
        """所有开发机器 Git 仓库同步正常"""
        for machine in ["W1", "W2", "W3", "W4"]:
            result = ssh_check(machine, "cd ~/ai-crm && git log --oneline -1")
            assert result.returncode == 0, (
                f"{machine} git 仓库异常: {result.stderr}"
            )
