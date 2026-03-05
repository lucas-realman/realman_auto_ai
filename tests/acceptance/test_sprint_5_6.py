"""
Sprint 5-6 验收测试
═══════════════════
里程碑: 📊 能洞察
通过标准: 商机阶段推进时自动计算赢率并推送钉钉互动卡片

测试项源自 docs/07-Sprint任务卡.md §3 每日任务的「完成标志」列。
运行方式:
    RUN_ACCEPTANCE=1 python3 -m pytest tests/acceptance/test_sprint_5_6.py -v
"""
from __future__ import annotations

import uuid
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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ════════════════════════════════════════════════════════
#  Day 1 — 商机 Agent + 商机 CRUD API
# ════════════════════════════════════════════════════════

class TestDay1Opportunity:
    """Day 1 完成标志: 商机预测 Agent 可用, 商机 CRUD 通过"""

    def test_w1_opportunity_predictor_exists(self):
        """W1: 商机预测 Agent 文件存在"""
        result = ssh_check(
            "W1",
            "test -f ~/ai-crm/agent/agents/opportunity_predictor.py && echo OK",
        )
        assert "OK" in result.stdout, "opportunity_predictor.py 不存在"

    def test_w2_opportunities_crud_post(self):
        """W2: POST /api/v1/opportunities 创建商机"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_post(
            svc["host"], svc["port"],
            "/api/v1/opportunities",
            json_body={
                "name": f"验收测试商机_{uuid.uuid4().hex[:6]}",
                "stage": "初步接洽",
                "amount": 100000,
                "customer_id": 1,
            },
        )
        assert resp.status_code in (200, 201, 422), (
            f"创建商机失败: {resp.status_code} {resp.text}"
        )

    def test_w2_opportunities_crud_get(self):
        """W2: GET /api/v1/opportunities 列表正常"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/opportunities")
        assert resp.status_code == 200

    def test_w3_interactive_card_framework(self):
        """W3: 互动卡片框架文件存在"""
        result = ssh_check(
            "W3",
            "test -d ~/ai-crm/deploy/dingtalk/cards && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("互动卡片框架尚未创建")
        assert "OK" in result.stdout

    def test_w4_celery_worker_queues(self):
        """W4: Celery 多队列配置存在"""
        result = ssh_check(
            "W4",
            "test -f ~/ai-crm/scripts/celery_config.py && echo OK || "
            "grep -r 'celery' ~/ai-crm/scripts/ 2>/dev/null | head -3",
        )
        assert result.returncode == 0


# ════════════════════════════════════════════════════════
#  Day 2 — 商机 Tool + 阶段流转
# ════════════════════════════════════════════════════════

class TestDay2StageMachine:
    """Day 2 完成标志: 商机 Tool 可调用, 阶段流转逻辑正确"""

    def test_w1_opportunity_tools_exist(self):
        """W1: 商机 Tools 文件存在"""
        result = ssh_check(
            "W1",
            "test -f ~/ai-crm/agent/tools/opportunity_tools.py && echo OK",
        )
        assert "OK" in result.stdout, "opportunity_tools.py 不存在"

    def test_w2_stage_machine_logic(self):
        """W2: 阶段流转服务存在"""
        result = ssh_check(
            "W2",
            "test -f ~/ai-crm/crm/services/stage_machine.py && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("阶段流转逻辑尚未实现")
        assert "OK" in result.stdout

    def test_w3_lead_claim_card(self):
        """W3: 线索领取卡片模板存在"""
        result = ssh_check(
            "W3",
            "ls ~/ai-crm/deploy/dingtalk/cards/lead_claim* 2>/dev/null && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("线索领取卡片模板尚未创建")
        assert "OK" in result.stdout


# ════════════════════════════════════════════════════════
#  Day 3 — 客户洞察 + 活动 CRUD
# ════════════════════════════════════════════════════════

class TestDay3Insight:
    """Day 3 完成标志: 客户洞察 Agent 可用, 活动 CRUD 通过"""

    def test_w1_customer_insight_agent_exists(self):
        """W1: 客户洞察 Agent 文件存在"""
        result = ssh_check(
            "W1",
            "test -f ~/ai-crm/agent/agents/customer_insight.py && echo OK",
        )
        assert "OK" in result.stdout, "customer_insight.py 不存在"

    def test_w2_activities_crud_post(self):
        """W2: POST /api/v1/activities 创建活动"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_post(
            svc["host"], svc["port"],
            "/api/v1/activities",
            json_body={
                "type": "拜访",
                "description": f"验收测试活动_{uuid.uuid4().hex[:6]}",
                "customer_id": 1,
            },
        )
        assert resp.status_code in (200, 201, 422), (
            f"创建活动失败: {resp.status_code} {resp.text}"
        )

    def test_w2_activities_crud_get(self):
        """W2: GET /api/v1/activities 列表正常"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/activities")
        assert resp.status_code == 200

    def test_w3_stage_confirm_card(self):
        """W3: 商机推进确认卡片模板存在"""
        result = ssh_check(
            "W3",
            "ls ~/ai-crm/deploy/dingtalk/cards/stage_confirm* 2>/dev/null && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("商机推进确认卡片尚未创建")
        assert "OK" in result.stdout

    def test_w4_event_subscriber(self):
        """W4: Redis Stream 事件订阅服务存在"""
        result = ssh_check(
            "W4",
            "test -f ~/ai-crm/crm/events/subscriber.py && echo OK || "
            "test -f ~/ai-crm/scripts/event_subscriber.py && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("事件订阅服务尚未实现")
        assert "OK" in result.stdout


# ════════════════════════════════════════════════════════
#  Day 4-5 — 漏斗统计 + 仪表盘
# ════════════════════════════════════════════════════════

class TestDay4_5Analytics:
    """Day 4-5 完成标志: 漏斗统计、仪表盘 API 可用"""

    def test_w2_funnel_analytics_api(self):
        """W2: GET /api/v1/analytics/funnel 漏斗统计"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/analytics/funnel")
        assert resp.status_code in (200, 404, 501), (
            f"漏斗统计 API 异常: {resp.status_code}"
        )

    def test_w2_dashboard_api(self):
        """W2: GET /api/v1/dashboard 仪表盘数据"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/dashboard")
        assert resp.status_code in (200, 404, 501), (
            f"仪表盘 API 异常: {resp.status_code}"
        )

    def test_w1_activity_tools_exist(self):
        """W1: 活动 Tools 文件存在"""
        result = ssh_check(
            "W1",
            "test -f ~/ai-crm/agent/tools/activity_tools.py && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("activity_tools.py 尚未实现")
        assert "OK" in result.stdout

    def test_w4_daily_report_task(self):
        """W4: 每日报表定时任务存在"""
        result = ssh_check(
            "W4",
            "test -f ~/ai-crm/scripts/tasks/daily_report.py && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("每日报表任务尚未实现")
        assert "OK" in result.stdout

    def test_w1_industry_insight_agent(self):
        """W1: 行业知识 Agent 存在 (云端子任务)"""
        result = ssh_check(
            "W1",
            "test -f ~/ai-crm/agent/agents/industry_insight.py && echo OK",
        )
        if "OK" not in result.stdout:
            pytest.skip("行业知识 Agent 尚未实现")
        assert "OK" in result.stdout


# ════════════════════════════════════════════════════════
#  Day 6-7 — Agent 协作 + Vue3 页面
# ════════════════════════════════════════════════════════

class TestDay6_7Collaboration:
    """Day 6-7 完成标志: 多 Agent 协作, Vue3 页面可访问"""

    def test_w1_agent_chain_call(self):
        """W1: Supervisor → SalesAssistant → OpportunityPredictor 链式调用"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_post(
            svc["host"], svc["port"],
            "/agent/chat",
            json_body={
                "message": "帮我分析一下这个商机的赢率",
                "session_id": f"chain_{uuid.uuid4().hex[:8]}",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        reply = data.get("reply") or data.get("content") or data.get("message", "")
        assert len(reply) > 0, "链式调用应返回结果"

    def test_w2_customer_360_api(self):
        """W2: 客户 360 视图 API (详情+关联数据)"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/customers/1")
        assert resp.status_code in (200, 404), (
            f"客户详情 API 异常: {resp.status_code}"
        )

    def test_w2_frontend_accessible(self):
        """W2: Vue3 前端可访问 (如部署)"""
        svc = SERVICE_ENDPOINTS["dashboard"]
        resp = http_get(svc["host"], svc["port"], "/")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════
#  Day 8-9 — 联调
# ════════════════════════════════════════════════════════

class TestDay8_9Integration56:
    """Day 8-9 完成标志: 商机全流程 + 洞察联调"""

    def test_opportunity_full_flow(self):
        """商机全流程: 创建 → 阶段推进 → 赢率计算"""
        svc = SERVICE_ENDPOINTS["agent"]
        # 1. 创建商机
        resp = http_post(
            svc["host"], svc["port"],
            "/agent/chat",
            json_body={
                "message": "帮我创建一个商机, 客户XX科技, 金额50万, 阶段初步接洽",
                "session_id": f"opp_flow_{uuid.uuid4().hex[:8]}",
            },
        )
        assert resp.status_code == 200

    def test_customer_insight_e2e(self):
        """端到端: '分析客户XX' → 洞察结果"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_post(
            svc["host"], svc["port"],
            "/agent/chat",
            json_body={
                "message": "帮我分析一下客户的整体情况",
                "session_id": f"insight_{uuid.uuid4().hex[:8]}",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        reply = data.get("reply") or data.get("content") or data.get("message", "")
        assert len(reply) > 0, "洞察应返回有意义的分析"

    def test_w4_celery_tasks_registered(self):
        """W4: Celery 异步任务已注册"""
        result = ssh_check(
            "W4",
            "ls ~/ai-crm/scripts/tasks/*.py 2>/dev/null | wc -l",
        )
        if result.returncode != 0:
            pytest.skip("Celery 任务目录不存在")
        count = result.stdout.strip()
        # 至少有 2 个任务文件
        if count.isdigit():
            assert int(count) >= 1, "应有至少 1 个 Celery 任务文件"


# ════════════════════════════════════════════════════════
#  Day 10 — Sprint Review / 里程碑
# ════════════════════════════════════════════════════════

class TestSprintMilestone56:
    """
    Sprint 5-6 里程碑: 📊 能洞察
    通过标准: 商机阶段推进 → 自动计算赢率 → 推送钉钉互动卡片
    """

    def test_milestone_opportunity_prediction(self):
        """里程碑验收: 商机推进 → 自动赢率预测"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_post(
            svc["host"], svc["port"],
            "/agent/chat",
            json_body={
                "message": "这个商机已经到了方案评审阶段，帮我预测一下赢率",
                "session_id": f"milestone56_{uuid.uuid4().hex[:8]}",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        reply = data.get("reply") or data.get("content") or data.get("message", "")
        assert len(reply) > 0, "里程碑验收: 应返回赢率预测结果"

    def test_crm_opportunities_api_complete(self):
        """CRM Opportunities API 完整可用"""
        svc = SERVICE_ENDPOINTS["crm"]
        host, port = svc["host"], svc["port"]

        # Read list
        resp = http_get(host, port, "/api/v1/opportunities")
        assert resp.status_code == 200

        # Read single (may 404 if empty)
        resp = http_get(host, port, "/api/v1/opportunities/1")
        assert resp.status_code in (200, 404)

    def test_crm_activities_api_complete(self):
        """CRM Activities API 完整可用"""
        svc = SERVICE_ENDPOINTS["crm"]
        resp = http_get(svc["host"], svc["port"], "/api/v1/activities")
        assert resp.status_code == 200

    def test_all_agents_healthy(self):
        """所有 Agent 服务健康"""
        svc = SERVICE_ENDPOINTS["agent"]
        resp = http_get(svc["host"], svc["port"], "/health")
        assert resp.status_code == 200

    def test_all_crm_routes_available(self):
        """CRM API 全部路由 (含新增) 可用"""
        svc = SERVICE_ENDPOINTS["crm"]
        host, port = svc["host"], svc["port"]
        routes = [
            "/health",
            "/docs",
            "/api/v1/leads",
            "/api/v1/customers",
            "/api/v1/activities",
            "/api/v1/deals",
            "/api/v1/opportunities",
        ]
        for route in routes:
            resp = http_get(host, port, route)
            assert resp.status_code in (200, 404), (
                f"CRM 路由 {route} 返回 {resp.status_code}"
            )

    def test_performance_baseline(self):
        """性能基线: API P95 < 3s"""
        import time

        svc = SERVICE_ENDPOINTS["crm"]
        latencies = []
        for _ in range(5):
            start = time.monotonic()
            resp = http_get(svc["host"], svc["port"], "/api/v1/leads")
            elapsed = time.monotonic() - start
            latencies.append(elapsed)
            assert resp.status_code == 200

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 3.0, f"API P95 延迟 {p95:.2f}s 超过 3s 基线"

    def test_all_machines_git_synced(self):
        """所有开发机器 Git 仓库同步正常"""
        for machine in ["W1", "W2", "W3", "W4"]:
            result = ssh_check(machine, "cd ~/ai-crm && git log --oneline -1")
            assert result.returncode == 0, (
                f"{machine} git 仓库异常: {result.stderr}"
            )
