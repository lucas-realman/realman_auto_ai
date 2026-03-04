# Sprint 1-2 基础批次 — 骨架代码生成
# 状态: 待执行 | 批次: foundation-batch-001

## 任务分配

| # | 机器 | SSH 别名 | 任务 | 目标目录 | 预计时间 |
|---|------|---------|------|---------|---------|
| T1 | 4090 | ssh 4090 | Agent 引擎骨架 + Supervisor Agent v0.1 | agent/ | 15 min |
| T2 | mac_min_8T | ssh mac_min_8T | CRM 后端骨架 + DB 模型 + Alembic 迁移 | crm/ | 15 min |
| T3 | gateway | ssh gateway | Nginx 反向代理 + DingTalk 回调桩 | deploy/nginx/ | 10 min |
| T4 | data_center | ssh data_center | 全节点健康检查脚本 + 开发辅助工具 | scripts/ | 10 min |

## 执行顺序

1. 并行: T1 + T2 + T3 + T4

## 各任务详细说明

### T1 — Agent 引擎骨架 (4090 → agent/)

在 `agent/` 目录下创建 FastAPI 应用，这是 Sirus AI CRM 的「大脑」。

**必须生成的文件:**
- `agent/__init__.py`
- `agent/main.py` — FastAPI app；挂载 CORS；包含 `POST /agent/chat`（接收用户消息、调用 Supervisor、返回 ChatResponse）和 `GET /health`（检查 vLLM + Redis 连通性，格式参照 contracts/health-api.yaml）
- `agent/config.py` — pydantic-settings 的 Settings 类；字段: VLLM_BASE_URL (default http://localhost:8000/v1), REDIS_URL (default redis://172.16.12.50:6379/0), OPENAI_API_KEY, MODEL_NAME (default qwen3-30b-a3b), APP_PORT (default 8100)
- `agent/supervisor.py` — SupervisorAgent 类；`async def route(message, session_id)` 方法：用 LLM Function Calling 做意图分类 → 委派到子 Agent（sales_assistant / lead_scoring / customer_insight）；先实现 sales_assistant 分支，其余返回"功能开发中"
- `agent/agents/__init__.py`
- `agent/agents/sales_assistant.py` — SalesAssistantAgent 类；接收 Supervisor 委派的消息，调用 CRM Tools（contracts/agent-tools.yaml 定义），返回自然语言结果；使用 openai.AsyncOpenAI 对 vLLM 发起 function calling；Tool 列表从 tools.py 导入
- `agent/tools.py` — 注册所有 Tool Calling 函数；函数内部通过 httpx.AsyncClient 调用 CRM API (http://172.16.12.50:8900/api/v1/...)；函数签名严格匹配 contracts/agent-tools.yaml
- `agent/session.py` — Redis 会话管理；save_message(session_id, role, content) / get_history(session_id, limit=20)
- `agent/requirements.txt` — fastapi, uvicorn[standard], openai>=1.0, httpx, redis[hiredis], pydantic-settings

**关键约束:**
- 使用 `openai.AsyncOpenAI(base_url=settings.VLLM_BASE_URL, api_key="EMPTY")` 调用本地 vLLM
- 所有 I/O 必须 async/await（AsyncOpenAI + httpx.AsyncClient）
- /agent/chat 响应格式严格遵循 contracts/agent-api.yaml 中的 ChatResponse
- Tool Calling 函数签名严格匹配 contracts/agent-tools.yaml

---

### T2 — CRM 后端骨架 (mac_min_8T → crm/)

在 `crm/` 目录下创建 FastAPI + SQLAlchemy + Alembic 应用，这是数据持久层。

**必须生成的文件:**
- `crm/__init__.py`
- `crm/main.py` — FastAPI app；挂载 CORS；挂载 leads, customers, opportunities, activities 四个 router；包含 `GET /health`（检查 PG 连接）
- `crm/config.py` — pydantic-settings 的 Settings 类；字段: DATABASE_URL (default postgresql+asyncpg://ai_crm:ai_crm_2026@localhost:5432/ai_crm), REDIS_URL (default redis://localhost:6379/0), APP_PORT (default 8900)
- `crm/database.py` — async SQLAlchemy engine + async sessionmaker + get_db dependency
- `crm/models/__init__.py` — 导出所有模型
- `crm/models/base.py` — DeclarativeBase + common columns (id UUID, created_at, updated_at, deleted_at)
- `crm/models/user.py` — User 模型（对应 contracts/db-schema.sql 中 users 表）
- `crm/models/lead.py` — Lead 模型
- `crm/models/customer.py` — Customer, Contact 模型
- `crm/models/opportunity.py` — Opportunity 模型
- `crm/models/activity.py` — Activity 模型
- `crm/models/audit_log.py` — AuditLog 模型
- `crm/schemas/__init__.py`
- `crm/schemas/lead.py` — LeadCreate, LeadUpdate, LeadResponse, PaginatedLeads（匹配 contracts/crm-api.yaml）
- `crm/schemas/customer.py` — CustomerCreate, CustomerUpdate, CustomerResponse, CustomerDetail, PaginatedCustomers
- `crm/schemas/opportunity.py` — OpportunityCreate, OpportunityUpdate, OpportunityResponse
- `crm/schemas/activity.py` — ActivityCreate, ActivityResponse
- `crm/api/__init__.py`
- `crm/api/leads.py` — /api/v1/leads CRUD router（严格匹配 contracts/crm-api.yaml）；包含 query_leads 的分页+搜索逻辑
- `crm/api/customers.py` — /api/v1/customers CRUD router + 360 度视图
- `crm/api/opportunities.py` — /api/v1/opportunities CRUD router + 阶段推进
- `crm/api/activities.py` — /api/v1/activities CRUD router
- `crm/services/__init__.py`
- `crm/services/audit.py` — 审计日志服务（每个 CRM 写操作自动记录到 audit_log）
- `crm/services/event_publisher.py` — Redis Stream 事件发布（格式匹配 contracts/event-bus.yaml）
- `crm/alembic.ini` — Alembic 配置（sqlalchemy.url 读取环境变量）
- `crm/alembic/env.py` — 标准 Alembic async 配置
- `crm/alembic/versions/.gitkeep`
- `crm/requirements.txt` — fastapi, uvicorn[standard], sqlalchemy[asyncio], asyncpg, alembic, redis, pydantic-settings, python-multipart

**关键约束:**
- SQLAlchemy 2.0 风格（select() 而非 query()）
- 所有数据库操作用 async session
- Lead/Customer/Opportunity 的软删除: WHERE deleted_at IS NULL
- 每个 CRM 写操作调用 audit.log_action() 记录审计
- 每个 CRM 写操作通过 event_publisher.publish() 发布 Redis Stream 事件
- 字段类型和名称严格匹配 contracts/db-schema.sql

---

### T3 — Nginx 反向代理 + DingTalk 回调桩 (gateway → deploy/nginx/)

在 `deploy/nginx/` 和 `deploy/dingtalk/` 目录下创建配置和桩服务。

**必须生成的文件:**
- `deploy/nginx/ai-crm.conf` — Nginx 配置:
  - `location /api/` → `proxy_pass http://172.16.12.50:8900/api/;`（CRM 后端）
  - `location /agent/` → `proxy_pass http://172.16.11.194:8100/agent/;`（Agent 引擎）
  - `location /health/crm` → `proxy_pass http://172.16.12.50:8900/health;`
  - `location /health/agent` → `proxy_pass http://172.16.11.194:8100/health;`
  - 支持 WebSocket/SSE (Upgrade, Connection, proxy_buffering off)
  - 安全 headers (X-Frame-Options, X-Content-Type-Options)
  - access_log / error_log 配置
  - 监听 80 端口
- `deploy/nginx/install.sh` — 安装脚本: 复制 conf → nginx -t → reload
- `deploy/dingtalk/stub_server.py` — DingTalk 回调桩 (FastAPI, port 9000):
  - `POST /dingtalk/callback` — 接收钉钉消息 → 转发到 Agent /agent/chat → 返回回复
  - `GET /health` — 健康检查
  - 使用 httpx.AsyncClient 调用 Agent API
- `deploy/dingtalk/config.py` — AGENT_URL, DINGTALK_TOKEN, APP_PORT(9000)
- `deploy/dingtalk/requirements.txt` — fastapi, uvicorn, httpx, pydantic-settings

**关键约束:**
- Nginx 不缓存 SSE 流式响应 (proxy_buffering off)
- DingTalk 桩只做消息转发，不做加密验签（S3 再实现）
- gateway 机器没有 sudo 权限用 realman 用户，Nginx 配置生成后需手动 link

---

### T4 — 健康检查脚本 + 开发辅助 (data_center → scripts/)

在 `scripts/` 目录下创建运维脚本。

**必须生成的文件:**
- `scripts/check_health.sh` — 巡检脚本:
  - 检查 CRM 后端: curl http://172.16.12.50:8900/health
  - 检查 Agent 引擎: curl http://172.16.11.194:8100/health
  - 检查 DingTalk 桩: curl http://172.16.14.215:9000/health
  - 检查 PostgreSQL: pg_isready -h 172.16.12.50 -p 5432
  - 检查 Redis: redis-cli -h 172.16.12.50 ping
  - 检查 vLLM: curl http://172.16.11.194:8000/health
  - 输出格式: 表格 (服务名 | 状态 | 响应时间)
  - 失败项红色高亮 (ANSI color)
- `scripts/dev_start.sh` — 开发环境启动:
  - SSH 到各机器启动对应服务 (uvicorn)
  - 4090: cd ~/ai-crm && uvicorn agent.main:app --host 0.0.0.0 --port 8100
  - mac_min_8T: cd ~/ai-crm && uvicorn crm.main:app --host 0.0.0.0 --port 8900
  - gateway: cd ~/ai-crm && uvicorn deploy.dingtalk.stub_server:app --host 0.0.0.0 --port 9000
  - 后台运行 (nohup + &)
- `scripts/dev_stop.sh` — 停止各服务 (pkill -f uvicorn)
- `scripts/dev_status.sh` — 检查各服务进程状态 + 查看最新日志

**关键约束:**
- 脚本可在任意机器执行（通过 SSH 连接其他机器）
- 使用 set -euo pipefail
- 带颜色输出 + 友好错误信息
