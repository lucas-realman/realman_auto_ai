# 睿尔曼智能 CRM — Sprint 任务卡

> **版本**: v2.0
> **依赖文档**: [04-系统概要设计.md](04-系统概要设计.md) §11 · [06-总体开发计划.md](06-总体开发计划.md)
> **使用方式**: Orchestrator 每个 Sprint 启动时自动读取本文档，解析为编码任务队列（也可人工查阅）
> **机器约定**: W0=orchestrator(Orchestrator调度+Review+测试+Staging), W1=4090(aider), W2=mac_min_8T(aider), W3=gateway(aider), W4=data_center(aider)
>
> **v2.1 变更**: aliyun-agent（云端 L20）已移除，全部业务在内网 5 台机器运行。W5 已取消，预发布验收由 W0 (orchestrator) 承担。

---

## 1. Sprint 1-2：基础设施 + 接口契约（W1-W2 周）

> **里程碑**: 🏗️ 能对话  
> **通过标准**: 钉钉发消息 → Agent 收到 → 调用 vLLM → 返回文字，端到端链路跑通  
> **前置条件**: 5 台机器 SSH 互通、aider 已安装、Orchestrator 调度脚本已就位（~200 行薄调度层，非重型系统）

### 1.1 任务总览

```
Sprint 1-2 任务分布 (10 个工作日)

         Day1    Day2    Day3    Day4    Day5  │  Day6    Day7    Day8    Day9    Day10
         ─────   ─────   ─────   ─────   ───── │  ─────   ─────   ─────   ─────   ─────
W1(4090) vLLM    vLLM    Agent   契约    Super │  路由器  模型    Agent   联调    冲刺
         部署    调优    骨架    编写    visor │  本地云  路由    整合    修复    验收
                                               │
W2(mac)  PG+     Schema  Fast    API     迁移  │  认证    种子    CRM     联调    冲刺
         Redis   设计    API骨   契约    执行  │  JWT     数据    整合    修复    验收
                                               │
W3(gw)   Nginx   钉钉    回调    代理    消息  │  路由    SSO     全链    联调    冲刺
         基础    注册    接入    规则    转发  │  完善    预备    路测    修复    验收
                                               │
W4(dc)   Git     自动    监控    契约    流水  │  备份    日志    Celery  联调    冲刺
         裸仓    化脚本  基础    review  线    │  脚本    收集    基础    修复    验收
                                               │
W5(stg)  OS      vLLM    Hook    评估    首次  │  (跟随 git push 自动触发评估，测试在 W0 本地执行)
         搭建    安装    配置    骨架    报告  │
```

### 1.2 逐日任务卡

#### Day 1 — 环境搭建

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | vLLM 部署 + GPU 验证 | "检查 2×4090 驱动状态，安装 vLLM，启动 Qwen3-30B-A3B 推理服务" | `scripts/start_vllm.sh` | `curl localhost:8000/v1/models` 返回模型名 |
| **W2** | PostgreSQL 16 + pgvector + Redis 7 安装 | "在 macOS 上用 brew 安装 PG16 + pgvector + Redis7，创建 ai_crm 数据库" | `scripts/init_db.sh` | `psql -c "SELECT 1"` + `redis-cli ping` 成功 |
| **W3** | Nginx 基础配置 | "生成 Nginx 基础配置，预留 /api/* 和 /agent/* 代理位置" | `deploy/nginx/nginx.conf` | `nginx -t` 通过 |
| **W4** | Git 裸仓库 + 5 机 clone | “在 mac_min_8T 上初始化 Git 裸仓库，编写 5 台机器的 clone 脚本” | `scripts/init_git.sh` | 5 台机器均可 `git push/pull` |
| **W5** | 操作系统环境搭建 | （参考 09-测试机搭建计划）Python 3.11 + CUDA 驱动 + 基础依赖 | — | `python --version` + `nvidia-smi` 正常 |

> **Day 1 收尾**: 5 个开发窗口 `git push`，确认 Git 仓库流通正常。

#### Day 2 — 基础服务调优

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | vLLM 推理调优 | "调整 tp_size=2、enable-prefix-caching、gpu-memory-utilization=0.85，跑基准测试" | `scripts/benchmark_vllm.sh` | TTFT < 2s, 吞吐 > 20 tok/s |
| **W2** | 数据库 Schema v1 设计 | "根据 01/02 需求文档设计 leads/customers/opportunities/activities 四张核心表的 Schema" | `contracts/db-schema.sql` | Schema 文件完成，字段无遗漏 |
| **W3** | 钉钉企业应用注册 | 手动操作：在钉钉开放平台注册企业内部应用，获取 AppKey/AppSecret | `docs/dingtalk-config.md` | 获得 AppKey + AppSecret |
| **W4** | 开发自动化脚本 | “编写 5 台机器的一键启动/停止/状态检查脚本” | `scripts/dev_start.sh`, `scripts/dev_stop.sh`, `scripts/dev_status.sh` | 脚本可执行，状态检查输出所有服务状态 |
| **W5** | vLLM 安装 + 模型部署 | L20 上安装 vLLM, 加载 Qwen3-30B-A3B（独立测试推理） | — | `curl localhost:8000/v1/models` 返回模型名 |

#### Day 3 — 项目骨架

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Agent 引擎骨架 | "创建 FastAPI 项目，包含 agent/ 目录结构、config、logging、health 端点" | `agent/__init__.py`, `agent/main.py`, `agent/config.py` | `uvicorn agent.main:app` 启动，`/health` 返回 200 |
| **W2** | CRM 后端骨架 | "创建 FastAPI 项目，包含 crm/ 目录结构、SQLAlchemy + Alembic 配置" | `crm/__init__.py`, `crm/main.py`, `crm/database.py` | `uvicorn crm.main:app` 启动，`/health` 返回 200 |
| **W3** | 钉钉回调接入 | "实现钉钉机器人消息回调接收端点，验签 + 解析消息体" | `deploy/nginx/dingtalk_callback.py` | 钉钉发测试消息，服务器日志可见 |
| **W4** | 健康检查 + 基础监控 | "编写各服务健康检查脚本，每 30s 轮询一次" | `scripts/health_check.sh` | 脚本正确报告各服务在线/离线状态 |
| **W5** | Git post-receive hook | "配置 post-receive hook，推送后 SSH 触发 orchestrator 本地自动测试" | `scripts/post-receive` | `git push` 后 orchestrator 本地触发 pytest |

#### Day 4 — 接口契约

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Agent 接口契约 | "根据 04-§5 和 §9 生成 agent-api.yaml（Agent 对外接口）和 agent-tools.yaml（Tool Calling Schema）" | `contracts/agent-api.yaml`, `contracts/agent-tools.yaml` | YAML 语法正确，覆盖 Supervisor + 销售助手 |
| **W2** | CRM 接口契约 | "根据 04-§9 生成 crm-api.yaml（线索/客户/商机/活动 CRUD 接口定义）" | `contracts/crm-api.yaml` | OpenAPI 3.0 格式，4 组资源 CRUD 完整 |
| **W3** | 反向代理规则 | "根据 contracts/ 中的端口和路径定义，完善 Nginx 代理规则" | `deploy/nginx/nginx.conf` (更新) | `/api/*` → mac_min:8900, `/agent/*` → 4090:8100 |
| **W4** | 事件总线契约 | "根据 04-§5.5 生成 event-bus.yaml（Redis Stream 事件格式定义）" | `contracts/event-bus.yaml` | 覆盖 lead.created / opportunity.stage_changed 等事件 |
| **W5** | 评估框架骨架 | pytest + 云端多模型 Judge 评估器框架搭建 | `tests/conftest.py`, `tests/eval/judge.py` | `pytest --collect-only` 可发现测试 |

> **Day 4 收尾**: contracts/ 目录完整，5 台机器 `git pull` 后都能看到统一的接口定义。

#### Day 5 — Week 1 集成验证

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Supervisor Agent v0.1 | "实现 Supervisor Agent 骨架：接收消息 → 调用 vLLM → 返回文字（不含 Tool Calling）" | `agent/supervisor.py`, `agent/prompts/supervisor.jinja2` | POST /agent/chat → vLLM 推理 → 返回文字 |
| **W2** | DB 迁移 + 验证 | "运行 Alembic 迁移创建 4 张核心表，插入 5 条种子数据验证" | `crm/migrations/versions/001_init.py` | 4 张表创建成功，SELECT 可查到种子数据 |
| **W3** | 消息转发闭环 | "钉钉消息 → Nginx → Agent 引擎端点，测试完整链路" | — | 钉钉发消息 → Agent 收到（日志可见） |
| **W4** | CI 流水线草稿 | "编写简单的 git push 后自动运行 pytest 的 hook 脚本" | `scripts/ci_hook.sh` | `git push` 后 data_center 跑一遍 pytest |
| **W5** | 首次自动评估 | 触发一次完整的评估流水线，生成首份报告 | `reports/eval_sprint1_day5.json` | 报告生成，包含基础指标 |

> **Week 1 检查点**: 能在钉钉发消息 → Nginx 转发 → Agent 收到 → vLLM 推理 → 返回（哪怕是纯文字回复）。

#### Day 6 — 模型路由器

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 模型路由器（本地/云端） | "实现 model_router.py：根据 task_type 和 risk_level 选择本地 vLLM 或云端 API" | `agent/router/model_router.py` | 本地推理 + 云端 API 均可调通 |
| **W2** | JWT 认证模块 | "实现 JWT 认证中间件：钉钉 SSO code → 换取 JWT → 接口鉴权" | `crm/auth/jwt_handler.py`, `crm/auth/middleware.py` | 带 JWT 请求通过，无 JWT 返回 401 |
| **W3** | 路由规则完善 | "Nginx 配置增加 WebSocket 支持（SSE 流式输出）和 CORS 头" | `deploy/nginx/nginx.conf` (更新) | SSE 流式返回不被 Nginx 截断 |
| **W4** | PG 自动备份脚本 | "编写每日凌晨 2 点 pg_dump 备份脚本，保留最近 7 天" | `scripts/pg_backup.sh`, `scripts/crontab_setup.sh` | cron 注册成功，手动执行备份正常 |
| **W5** | (自动) 评估推送后代码 | — | — | 报告更新 |

#### Day 7 — 数据对齐

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Agent 对话上下文（Redis） | "实现对话上下文管理：session_id → Redis 存取最近 10 轮对话" | `agent/memory/working_memory.py` | 连续对话保持上下文，Redis 可查 |
| **W2** | 种子数据 + 测试数据 | "生成 50 条模拟线索、20 个客户、10 个商机的种子数据脚本" | `scripts/seed_data.py` | 执行后 DB 中有完整模拟数据 |
| **W3** | 钉钉 SSO 对接预备 | "实现钉钉 OAuth2 授权码模式流程（免登 → 获取用户信息）" | `deploy/dingtalk/sso.py` | 钉钉工作台点击 → 获取用户身份 |
| **W4** | 结构化日志收集 | "配置 Loguru JSON 格式日志，所有服务写入统一目录" | `scripts/log_config.py` | 各服务日志写入 /var/log/ai-crm/*.jsonl |
| **W5** | (自动) 评估 | — | — | — |

#### Day 8 — 整合联通

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Agent → CRM API 调通 | "Agent 引擎调用 CRM 后端的 /health 和 /api/v1/leads 接口，验证网络连通" | `agent/clients/crm_client.py` | Agent 可通过内网调用 CRM API |
| **W2** | CRM 列表 API (只读) | "实现 leads 和 customers 的 GET 列表接口（分页 + 搜索），用于联调验证" | `crm/api/leads.py`, `crm/api/customers.py` | GET /api/v1/leads?page=1 返回数据 |
| **W3** | 端到端消息链路 | "测试：钉钉 → Nginx → Agent → vLLM → 返回文字 → Nginx → 钉钉" | — | 钉钉发"你好"，收到 Agent 回复 |
| **W4** | Celery 基础搭建 | "搭建 Celery + Redis Broker，实现一个 hello_task 验证" | `scripts/celery_config.py` | `celery -A tasks worker` 启动正常 |
| **W5** | (自动) 评估全链路 | — | — | 报告包含 API 连通性指标 |

#### Day 9 — 联调修复

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1-W4** | 跨窗口联调 | 端到端测试：钉钉消息 → Agent → vLLM → 返回。修复发现的所有联通问题 | — | 端到端链路稳定运行 |
| **W5** | 查看评估报告 | 查看红灯项，回对应窗口修复 | — | 评估报告无红灯 |

> **Day 9 目标**: 所有已知的联通问题修复完毕，端到端链路可以稳定重复执行。

#### Day 10 — Sprint Review

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1-W4** | 冲刺验收 | 验证里程碑通过标准；补充测试用例；更新文档 | `docs/sprint1-2-review.md` | ✅ 里程碑"能对话"通过 |
| **W5** | 最终评估报告 | 查看 Sprint 1-2 综合评估报告 | `reports/eval_sprint1-2_final.json` | 基线评分记录 |
| **全员** | Sprint 3-4 规划 | 阅读 07-§2 任务卡，明确下一 Sprint 目标 | — | 任务卡确认 |

### 1.3 Sprint 1-2 交付物清单

| # | 交付物 | 所在窗口 | 路径 |
|---|--------|---------|------|
| D1 | vLLM 推理服务（常驻） | W1 | `scripts/start_vllm.sh` |
| D2 | Agent 引擎骨架 | W1 | `agent/` |
| D3 | Supervisor Agent v0.1 | W1 | `agent/supervisor.py` |
| D4 | 模型路由器 | W1 | `agent/router/model_router.py` |
| D5 | 对话上下文管理 | W1 | `agent/memory/working_memory.py` |
| D6 | PostgreSQL + pgvector + Redis | W2 | `scripts/init_db.sh` |
| D7 | 数据库 Schema v1 (4 张表) | W2 | `contracts/db-schema.sql` |
| D8 | CRM 后端骨架 | W2 | `crm/` |
| D9 | JWT 认证模块 | W2 | `crm/auth/` |
| D10 | Nginx 反向代理 | W3 | `deploy/nginx/nginx.conf` |
| D11 | 钉钉回调接收 | W3 | `deploy/dingtalk/` |
| D12 | Git 裸仓库 + 自动化脚本 | W4 | `scripts/` |
| D13 | 接口契约 v1 (5 文件) | 共享 | `contracts/` |
| D14 | 评估流水线 | W5 | `tests/` |

### 1.4 Sprint 1-2 风险检查点

| Day | 检查项 | 如果失败 |
|-----|--------|---------|
| Day 1 | vLLM 能在 2×4090 上加载模型 | 检查 CUDA 驱动、显存；降级为单卡 tp=1 |
| Day 2 | vLLM TTFT < 2s | 调整 max_model_len、batch_size；考虑 Qwen3.5-35B-A3B |
| Day 3 | 5 台机器 Git 互通 | 检查 SSH 密钥、网络路由 |
| Day 5 | 钉钉消息能到达 Agent | 检查 Nginx 代理、钉钉回调配置 |
| Day 8 | 端到端链路跑通 | 逐段排查：钉钉→Nginx→Agent→vLLM |
| Day 10 | 里程碑"能对话"通过 | 延长 1-2 天冲刺；砍掉模型路由器等非关键项 |

---

## 2. Sprint 3-4：销售助手 Agent + 线索/客户（W3-W4 周）

> **里程碑**: 📇 能做 CRM  
> **通过标准**: 销售在钉钉说"帮我创建一个线索，XX公司张总13800138000"，Agent 完成创建并返回确认  
> **前置条件**: Sprint 1-2 里程碑通过（能对话），接口契约 v1 就绪

### 2.1 任务总览

```
Sprint 3-4 任务分布 (10 个工作日)

         Day1    Day2    Day3    Day4    Day5  │  Day6    Day7    Day8    Day9    Day10
         ─────   ─────   ─────   ─────   ───── │  ─────   ─────   ─────   ─────   ─────
W1(4090) 销售    Tool    Tool    线索    意图  │  云端    Prompt  Agent   联调    冲刺
         助手    create  query   评分    增强  │  脱敏    调优    整合    修复    验收
         Agent   _lead   _lead   Agent          │
                                               │
W2(mac)  线索    线索    客户    线索池  SSO   │  种子    列表    详情    联调    冲刺
         CRUD    搜索    CRUD    逻辑    JWT   │  数据    页面    页面    修复    验收
         API     +分页   API                   │
                                               │
W3(gw)   钉钉    对话    卡片    SSO     消息  │  错误    流式    全链    联调    冲刺
         机器人  闭环    模板    联调    格式  │  处理    优化    路测    修复    验收
                                               │
W4(dc)   审计    审计    备份    事件    定时  │  日志    告警    监控    联调    冲刺
         日志表  写入    验证    日志    任务  │  分析    规则    面板    修复    验收
                                               │
W5(stg)  (自动跟随 git push 触发：Agent 评估 + API 测试 + 评分基线，测试在 W0 本地执行)
```

### 2.2 逐日任务卡

#### Day 1 — 销售助手 Agent + 线索 API

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 销售助手 Agent 框架 | "实现 SalesAssistant Agent：接收 Supervisor 委派 → 解析 CRM 意图（创建/查询/更新）→ 调用对应 Tool" | `agent/agents/sales_assistant.py`, `agent/prompts/sales_assistant.jinja2` | Agent 能识别"创建线索"意图 |
| **W2** | 线索 CRUD API | "根据 contracts/crm-api.yaml 实现 leads 的 POST/GET/PUT/DELETE 接口 + Pydantic Schema" | `crm/api/leads.py`, `crm/schemas/lead.py` | 4 个端点 curl 测试通过 |
| **W3** | 钉钉机器人对话闭环 | "完善钉钉回调：消息 → Agent → 回复文字 → 钉钉推送回用户" | `deploy/dingtalk/bot.py` | 钉钉发消息能收到 Agent 回复 |
| **W4** | 审计日志表 | "根据 04-§8.4 创建 audit_log 表 + SQLAlchemy 模型" | `crm/models/audit_log.py`, `crm/migrations/versions/002_audit.py` | 表创建成功 |

#### Day 2 — Tool Calling 实现

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | create_lead + create_customer Tool | "根据 contracts/agent-tools.yaml 实现 create_lead 和 create_customer 两个 Tool" | `agent/tools/crm_tools.py` | Tool 函数可独立调用，返回结构化结果 |
| **W2** | 线索搜索 + 分页 | "给 leads GET 接口增加关键词搜索、分页（page/size）、排序功能" | `crm/api/leads.py` (更新) | `GET /api/v1/leads?q=张&page=1&size=10` 正确返回 |
| **W3** | 对话闭环优化 | "处理多轮对话：用户确认/取消操作、Agent 二次确认高风险操作" | `deploy/dingtalk/conversation.py` | 多轮对话正常流转 |
| **W4** | 审计日志写入中间件 | "实现 FastAPI 中间件：每个写操作自动写入 audit_log" | `crm/middleware/audit.py` | POST/PUT/DELETE 操作后 audit_log 有记录 |

#### Day 3 — 客户模块 + 查询 Tool

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | query_lead + query_customer Tool | "实现查询类 Tool：支持按公司名/联系人/手机号模糊搜索" | `agent/tools/crm_tools.py` (更新) | "查一下张总的线索" → 正确返回 |
| **W2** | 客户 CRUD API | "根据 contracts/crm-api.yaml 实现 customers 的完整 CRUD + 线索→客户转化接口" | `crm/api/customers.py`, `crm/schemas/customer.py` | 4 个端点 + 转化接口测试通过 |
| **W3** | 钉钉互动卡片模板 | "实现线索创建确认卡片模板（含确认/取消按钮）" | `deploy/dingtalk/cards/lead_confirm.json` | 钉钉显示卡片，按钮可点击 |
| **W4** | PG 备份验证 | "验证自动备份是否正常运行，编写备份恢复测试脚本" | `scripts/pg_restore_test.sh` | 备份可成功恢复到测试库 |

#### Day 4 — 线索评分 + 线索池

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 线索评分 Agent（云端） | "实现 LeadScoring Agent：线索创建后自动评分（走云端 API，需脱敏）" | `agent/agents/lead_scoring.py`, `agent/prompts/lead_scoring.jinja2` | 线索创建 → 自动打分（1-100 分） |
| **W2** | 线索池分配逻辑 | "实现线索池：未分配线索入池，支持手动领取 + 按规则自动分配" | `crm/services/lead_pool.py`, `crm/api/lead_pool.py` | 线索入池 → 销售领取 → 分配成功 |
| **W3** | 钉钉 SSO 联调 | "完善 SSO：钉钉免登码 → 换取用户信息 → 生成 JWT → 后续请求鉴权" | `deploy/dingtalk/sso.py` (更新) | 钉钉登录 → 获取用户身份 |
| **W4** | 事件日志记录 | "每个 CRM 操作发布到 Redis Stream，格式参考 contracts/event-bus.yaml" | `crm/events/publisher.py` | Redis `XREAD` 可获取操作事件 |

#### Day 5 — 意图增强 + 种子数据

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Supervisor 意图识别增强 | "增强 Supervisor：识别 create_lead / query_lead / update_lead / convert_to_customer 等细分意图" | `agent/supervisor.py` (更新) | 10 条测试语句意图识别准确率 ≥ 80% |
| **W2** | SSO + JWT 集成 | "CRM 后端集成 JWT 认证，钉钉 SSO 获取的身份传入所有 API" | `crm/auth/` (更新) | 无 JWT → 401，有 JWT → 正常操作 |
| **W3** | 消息格式优化 | "Agent 回复支持 Markdown 格式，列表数据用表格展示" | — | 钉钉收到格式化回复 |
| **W4** | 定时评分任务 | "Celery Beat 定时任务：每小时对未评分线索批量调用线索评分 Agent" | `scripts/tasks/lead_scoring_task.py` | 定时任务注册成功，手动触发可批量评分 |

#### Day 6 — 云端脱敏 + 批量数据

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 云端 API 脱敏层 | "实现脱敏层：发送到云端前移除手机号/邮箱/姓名等 PII，返回后回填" | `agent/router/sanitizer.py` | 云端请求不含 PII，回填后数据完整 |
| **W2** | 批量种子数据 | "生成 100 条线索 + 30 个客户的真实感模拟数据" | `scripts/seed_data_v2.py` | DB 中有丰富的测试数据 |
| **W3** | 错误处理优化 | "完善错误处理：Agent 异常 → 友好提示；CRM 异常 → 重试 + 告知" | — | 各类异常场景均有友好提示 |
| **W4** | 日志分析脚本 | "编写日志分析工具：统计 Agent 调用量、错误率、平均响应时间" | `scripts/log_analyzer.py` | 输出每日统计摘要 |

#### Day 7 — Prompt 调优 + 页面

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Prompt A/B 调优 | "根据 W5 评估报告调优 Supervisor + SalesAssistant 的 Prompt，提高意图识别率" | Prompt 文件更新 | 多模型 Judge 加权评分 ≥ 3.5 |
| **W2** | 线索列表 Vue3 页面 (可选) | "生成线索列表页面：Element Plus 表格 + 搜索 + 分页 + 状态筛选" | `frontend/src/views/LeadList.vue` | 浏览器访问可见列表 |
| **W3** | 流式输出优化 | "Agent 回复走 SSE 流式推送，钉钉端逐步展示" | — | 长回复不卡顿，逐步显示 |
| **W4** | 告警规则 | "当 Agent 错误率 > 10% 或响应时间 > 5s 时推送钉钉告警" | `scripts/alert_rules.py` | 模拟异常时收到告警消息 |

#### Day 8-9 — 联调修复

| 窗口 | 任务 | 完成标志 |
|------|------|---------|
| **W1-W4** | 端到端联调："创建线索张总" → Agent → Tool → CRM API → DB → 确认消息 | 10 条典型指令全部成功 |
| **W1-W4** | 修复联调发现的问题：接口参数不匹配、Prompt 效果不佳等 | 所有已知 Bug 修复 |
| **W5** | 查看评估报告，确认自动化测试覆盖率 | 50+ 测试用例跑通 |

#### Day 10 — Sprint Review

| 窗口 | 任务 | 完成标志 |
|------|------|---------|
| **全员** | 验证里程碑"能做 CRM"通过 | ✅ 钉钉发"创建线索"→ Agent 完成 |
| **全员** | Agent 评估基线建立 | 多模型 Judge 加权评分 ≥ 3.5 → 记为基线 |
| **全员** | Sprint 5-6 规划 | 阅读 07-§3 任务卡 |

### 2.3 Sprint 3-4 交付物清单

| # | 交付物 | 窗口 | 关键文件 |
|---|--------|------|---------|
| D1 | 销售助手 Agent | W1 | `agent/agents/sales_assistant.py` |
| D2 | 线索评分 Agent (云端) | W1 | `agent/agents/lead_scoring.py` |
| D3 | CRM Tool ×5 | W1 | `agent/tools/crm_tools.py` |
| D4 | 云端脱敏层 | W1 | `agent/router/sanitizer.py` |
| D5 | 线索 CRUD API | W2 | `crm/api/leads.py` |
| D6 | 客户 CRUD API | W2 | `crm/api/customers.py` |
| D7 | 线索池分配逻辑 | W2 | `crm/services/lead_pool.py` |
| D8 | JWT 认证 | W2 | `crm/auth/` |
| D9 | 钉钉机器人闭环 | W3 | `deploy/dingtalk/` |
| D10 | 钉钉 SSO | W3 | `deploy/dingtalk/sso.py` |
| D11 | 审计日志 | W4 | `crm/middleware/audit.py` |
| D12 | 50+ 测试用例 | W5 | `tests/` |

---

## 3. Sprint 5-6：商机/活动 + AI 洞察（W5-W6 周）

> **里程碑**: 📊 能洞察  
> **通过标准**: 商机阶段推进时自动计算赢率并推送钉钉互动卡片  
> **前置条件**: Sprint 3-4 里程碑通过（能做 CRM），销售助手 Agent 稳定运行

### 3.1 任务总览

```
Sprint 5-6 任务分布 (10 个工作日)

         Day1    Day2    Day3    Day4    Day5  │  Day6    Day7    Day8    Day9    Day10
         ─────   ─────   ─────   ─────   ───── │  ─────   ─────   ─────   ─────   ─────
W1(4090) 商机    商机    客户    活动    行业  │  Agent   Prompt  多Agent  联调    冲刺
         预测    Tool    洞察    Tool    知识  │  协作    调优    联动    修复    验收
         Agent   ×3     Agent   ×2     云端  │
                                               │
W2(mac)  商机    阶段    活动    漏斗    统计  │  客户    Vue3    Vue3    联调    冲刺
         CRUD    流转    CRUD    统计    接口  │  详情    商机列  漏斗图  修复    验收
         API     逻辑    API     接口         │  页面    表页面
                                               │
W3(gw)   互动    线索    商机    卡片    消息  │  通知    卡片    全链    联调    冲刺
         卡片    领取    推进    回调    聚合  │  策略    模板库  路测    修复    验收
         框架    卡片    卡片                  │
                                               │
W4(dc)   Celery  异步    事件    报表    仪表  │  缓存    任务    监控    联调    冲刺
         Worker  评分    订阅    定时    盘数  │  优化    调度    完善    修复    验收
         搭建    任务    扩展    生成    据    │
                                               │
W5(stg)  (自动跟随 git push：150+ 测试用例，Agent 对话质量评估，性能基线，测试在 W0 本地执行)
```

### 3.2 逐日任务卡

#### Day 1 — 商机 Agent + API

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 商机预测 Agent | "实现 OpportunityPredictor Agent：分析商机数据 → 计算赢率 → 给出推进建议" | `agent/agents/opportunity_predictor.py`, `agent/prompts/opportunity.jinja2` | 输入商机信息 → 输出赢率 + 建议 |
| **W2** | 商机 CRUD API | "根据 contracts/crm-api.yaml 实现 opportunities 的完整 CRUD + 阶段字段" | `crm/api/opportunities.py`, `crm/schemas/opportunity.py` | 4 个端点测试通过 |
| **W3** | 钉钉互动卡片框架 | "实现互动卡片发送/回调框架：卡片发送 + 按钮点击回调处理" | `deploy/dingtalk/cards/card_manager.py` | 卡片发送成功，按钮回调可接收 |
| **W4** | Celery Worker 扩展 | "扩展 Celery Worker：支持多队列（scoring/prediction/report）" | `scripts/celery_config.py` (更新) | 3 个队列注册成功 |

#### Day 2 — Tool + 阶段流转

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 商机 Tool ×3 | "实现 create_opportunity / query_opportunity / update_opportunity_stage Tool" | `agent/tools/opportunity_tools.py` | 3 个 Tool 可独立调用 |
| **W2** | 阶段流转逻辑 | "实现商机阶段状态机：初步接洽→需求确认→方案评审→商务谈判→赢单/丢单，含流转校验" | `crm/services/stage_machine.py` | 阶段只能前进不能跳级，丢单可从任意阶段 |
| **W3** | 线索领取互动卡片 | "实现线索池领取卡片：显示线索摘要 + '领取'按钮 → 点击后分配给当前用户" | `deploy/dingtalk/cards/lead_claim.json` | 点击领取 → 线索分配成功 |
| **W4** | 异步评分任务扩展 | "商机创建/阶段变更时自动触发赢率计算（Celery 异步任务）" | `scripts/tasks/prediction_task.py` | 商机变更 → 自动计算赢率 |

#### Day 3 — 客户洞察 + 活动

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 客户洞察 Agent | "实现 CustomerInsight Agent：汇总客户的线索/商机/活动历史 → 生成客户画像 + 维护建议" | `agent/agents/customer_insight.py`, `agent/prompts/customer_insight.jinja2` | "分析一下 XX客户" → 输出画像 |
| **W2** | 活动 CRUD API | "根据 contracts/crm-api.yaml 实现 activities 的 CRUD + 按客户/商机关联查询" | `crm/api/activities.py`, `crm/schemas/activity.py` | 活动关联商机/客户查询正常 |
| **W3** | 商机推进确认卡片 | "商机阶段推进时推送互动卡片：显示变更内容 + '确认推进'/'暂缓'按钮" | `deploy/dingtalk/cards/stage_confirm.json` | 阶段推进 → 卡片推送 → 确认操作 |
| **W4** | 事件订阅扩展 | "扩展 Redis Stream 订阅：opportunity.stage_changed → 触发赢率重算 + 卡片推送" | `crm/events/subscriber.py` | 事件触发链条完整 |

#### Day 4 — 活动 Tool + 漏斗

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 活动 Tool ×2 | "实现 create_activity / query_activities Tool" | `agent/tools/activity_tools.py` | "记录一下今天拜访了 XX" → 活动创建 |
| **W2** | 漏斗统计接口 | "实现漏斗统计 API：各阶段商机数量/金额、转化率、平均停留天数" | `crm/api/analytics.py` | GET /api/v1/analytics/funnel 返回完整数据 |
| **W3** | 卡片按钮回调处理 | "完善所有卡片类型的按钮回调：确认/取消/领取 → 调用对应 CRM API" | `deploy/dingtalk/cards/callback_handler.py` | 所有按钮点击正确执行后端操作 |
| **W4** | 报表定时生成 | "Celery Beat 每日 8:00 生成昨日销售简报（线索数/商机数/转化率）" | `scripts/tasks/daily_report.py` | 定时任务注册，手动触发可生成报表 |

#### Day 5 — 云端子任务 + 统计

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 行业知识子任务（云端） | "Supervisor 识别到行业问题 → 脱敏后走云端 API → 获取行业洞察" | `agent/agents/industry_insight.py` | "XX客户所在行业趋势" → 云端返回分析 |
| **W2** | 综合统计接口 | "实现仪表盘统计 API：线索数/客户数/商机总金额/转化率/本月新增" | `crm/api/dashboard.py` | GET /api/v1/dashboard 返回汇总数据 |
| **W3** | 消息聚合推送 | "同一用户 5 分钟内的多条消息合并为一条卡片推送" | `deploy/dingtalk/message_aggregator.py` | 不轰炸用户，合并推送 |
| **W4** | 仪表盘数据聚合 | "Celery 异步计算仪表盘数据，结果缓存到 Redis（5 分钟过期）" | `scripts/tasks/dashboard_cache.py` | 仪表盘 API 响应 < 200ms |

#### Day 6-7 — Agent 协作 + Vue3 页面

| 窗口 | Day 6 任务 | Day 7 任务 |
|------|-----------|-----------|
| **W1** | Agent 间协作：Supervisor → SalesAssistant → OpportunityPredictor 链式调用 | Prompt 调优：根据 W5 报告优化所有 Agent Prompt |
| **W2** | 客户详情页 API（360 视图：基本信息+关联线索+商机+活动） | Vue3 商机列表页 + 漏斗图页面（ECharts） |
| **W3** | 通知策略：按紧急程度分级（立即推送 / 聚合推送 / 静默记录） | 卡片模板库整理：统一样式和交互模式 |
| **W4** | Redis 缓存优化：热点查询走缓存 | 任务调度优化：错峰执行，避免资源竞争 |

#### Day 8-9 — 联调 + 修复

| 窗口 | 任务 | 完成标志 |
|------|------|---------|
| **W1-W4** | 商机全流程联调：创建商机 → 阶段推进 → 赢率计算 → 卡片推送 → 确认 | 全流程无断点 |
| **W1-W4** | 洞察联调："分析客户 XX" → Agent 汇总历史 → 生成画像 + 建议 | 洞察结果合理 |
| **W5** | 评估报告：Agent 对话质量、Tool 调用准确率、性能度量 | 150+ 用例覆盖 |

#### Day 10 — Sprint Review

| 任务 | 完成标志 |
|------|---------|
| 验证里程碑"能洞察"通过 | ✅ 商机推进 → 自动赢率 + 钉钉卡片 |
| 性能基线建立 | API P95 < 3s, Agent 评分 ≥ 4.0 |
| Sprint 7-8 规划 | 阅读 07-§4 任务卡 |

### 3.3 Sprint 5-6 交付物清单

| # | 交付物 | 窗口 | 关键文件 |
|---|--------|------|---------|
| D1 | 商机预测 Agent | W1 | `agent/agents/opportunity_predictor.py` |
| D2 | 客户洞察 Agent | W1 | `agent/agents/customer_insight.py` |
| D3 | CRM Tool ×6 (商机×3+活动×2+行业×1) | W1 | `agent/tools/` |
| D4 | 商机 CRUD + 阶段流转 API | W2 | `crm/api/opportunities.py` |
| D5 | 活动 CRUD API | W2 | `crm/api/activities.py` |
| D6 | 漏斗统计 + 仪表盘 API | W2 | `crm/api/analytics.py`, `crm/api/dashboard.py` |
| D7 | 互动卡片 ×3 (领取+推进+确认) | W3 | `deploy/dingtalk/cards/` |
| D8 | Celery 异步任务 ×4 | W4 | `scripts/tasks/` |
| D9 | 150+ 测试用例 + 性能基线 | W5 | `tests/`, `reports/` |

---

## 4. Sprint 7-8：Web 看板 + 联调 + 上线（W7-W8 周）

> **里程碑**: 🚀 一期上线  
> **通过标准**: 全功能端到端可用，从开发模式切换到运行模式  
> **前置条件**: Sprint 5-6 里程碑通过（能洞察），6 个 Agent + 11 个 Tool 基本可用

### 4.1 任务总览

```
Sprint 7-8 任务分布 (10 个工作日)

         Day1    Day2    Day3    Day4    Day5  │  Day6    Day7    Day8    Day9    Day10
         ─────   ─────   ─────   ─────   ───── │  ─────   ─────   ─────   ─────   ─────
W1(4090) 行为    降级    Prompt  全量    全量  │  性能    稳定    Prompt  最终    上线
         分析    逻辑    调优    Agent   Agent │  优化    性测    最终    联调    切换
         Agent           迭代    联调    联调  │         试24h   版本
                                               │
W2(mac)  仪表    线索    客户    商机    活动  │  API     Docker  前端    最终    上线
         盘页    列表    详情    看板    列表  │  优化    化部署  优化    联调    切换
         面      页面    页面    页面    页面  │
                                               │
W3(gw)   SSL     限流    完整    安全    全链  │  Nginx   钉钉    异常    最终    上线
         证书    配置    路由    加固    路测  │  调优    最终    处理    联调    切换
                                               │         联调
                                               │
W4(dc)   Prome   Grafana PG流   日志    监控  │  告警    运维    备份    最终    上线
         theus   面板    复制    归集    全量  │  策略    文档    验证    联调    切换
         部署                                  │
                                               │
W5(stg)  (自动: 300+ 测试用例，E2E 验收，性能回归，稳定性报告，测试在 W0 本地执行)
```

### 4.2 逐日任务卡

#### Day 1 — 最后一个 Agent + 仪表盘

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 行为分析 Agent（云端） | "实现 BehaviorAnalysis Agent：分析用户操作模式 → 预测流失/购买倾向（走云端 API）" | `agent/agents/behavior_analysis.py` | 输入客户 ID → 输出行为分析报告 |
| **W2** | 仪表盘 Vue3 页面 | "用 Vue3 + Element Plus + ECharts 实现仪表盘：KPI 卡片 + 漏斗图 + 趋势图 + 待办列表" | `frontend/src/views/Dashboard.vue` | 浏览器访问可见完整仪表盘 |
| **W3** | SSL 证书配置 | "Nginx 配置 SSL（Let's Encrypt 或自签），强制 HTTPS" | `deploy/nginx/ssl.conf` | HTTPS 访问正常 |
| **W4** | Prometheus 部署 | “用 Docker 部署 Prometheus，配置 scrape 规则采集 5 台机器指标” | `deploy/monitoring/prometheus.yml`, `deploy/monitoring/docker-compose.yml` | Prometheus UI 可见各服务指标 |

#### Day 2 — 列表页面 + 限流 + Grafana

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Agent 降级逻辑完善 | "完善所有 Agent 的降级路径：vLLM 超时→重试→云端→友好提示" | `agent/middleware/fallback.py` | 模拟 vLLM 宕机时 Agent 优雅降级 |
| **W2** | 线索列表 Vue3 页面 | "线索列表页：表格+搜索+状态筛选+批量操作+创建弹窗" | `frontend/src/views/LeadList.vue` | CRUD 操作正常 |
| **W3** | Nginx 限流配置 | "配置 API 限流：单 IP 100 req/min，Agent 接口 30 req/min" | `deploy/nginx/rate_limit.conf` | 超限返回 429 |
| **W4** | Grafana 监控面板 | "配置 Grafana 面板：vLLM 吞吐/延迟、CRM API QPS/错误率、系统资源" | `deploy/monitoring/grafana_dashboards/` | Grafana 面板展示实时数据 |

#### Day 3 — 详情页 + 路由 + 流复制

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Prompt 调优（第 1 轮） | "根据 W5 评估报告，全面优化 Supervisor + 销售助手 + 各洞察 Agent 的 Prompt" | Prompt 文件更新 | 多模型 Judge 加权评分 ≥ 4.0 |
| **W2** | 客户详情 Vue3 页面 | "客户 360 视图页：基本信息+关联线索+商机时间线+活动记录+洞察卡片" | `frontend/src/views/CustomerDetail.vue` | 详情页数据正确展示 |
| **W3** | 完整反向代理路由 | "最终版 Nginx 配置：前端静态文件 + API + Agent + WebSocket + 钉钉回调" | `deploy/nginx/nginx.conf` (最终版) | 所有路由正确转发 |
| **W4** | PG 主从流复制 | "配置 mac_min_8T → data_center 的 PG 流复制热备" | `deploy/pg/replication.conf` | 主库写入 → 备库同步 |

#### Day 4 — 商机看板 + 全量 Agent 联调开始

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 全量 Agent 联调（Day 1/2） | "6 个 Agent 全量联调：Supervisor 分发 → 各 Agent 执行 → Tool 调用 → 返回" | — | 6 Agent × 3 场景 = 18 组测试通过 |
| **W2** | 商机看板 Vue3 页面 | "商机看板：阶段泳道（拖拽移动）+ 金额汇总 + 赢率色标" | `frontend/src/views/OpportunityBoard.vue` | 拖拽推进阶段正常 |
| **W3** | 安全加固 | "CORS 白名单、CSRF 防护、请求头安全策略、敏感接口限频" | `deploy/nginx/security.conf` | 安全扫描无高危项 |
| **W4** | 日志归集 | "所有服务的日志汇集到 data_center，按天滚动，保留 30 天" | `scripts/log_rotate.sh` | 统一日志目录可查 |

#### Day 5 — 活动页面 + 全链路 + 监控

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 全量 Agent 联调（Day 2/2） | 修复 Day 4 发现的问题，补充边界情况处理 | — | 所有联调问题修复 |
| **W2** | 活动列表 Vue3 页面 | "活动时间线视图 + 列表视图切换" | `frontend/src/views/ActivityList.vue` | 两种视图切换正常 |
| **W3** | 全链路端到端测试 | 钉钉 → Nginx → Agent → CRM → DB → 返回 → 钉钉，全部路径验证 | — | 所有链路通畅 |
| **W4** | 监控全量配置 | "所有服务添加 /metrics 端点，Prometheus 全量采集" | — | Grafana 面板数据完整 |

#### Day 6 — 性能优化

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | vLLM 性能调优 | "优化并发处理：调整 max_num_seqs、gpu_memory_utilization、prefix caching 参数" | — | 5 并发请求 P95 TTFT < 2s |
| **W2** | API 性能优化 | "慢查询优化：加索引、分页优化、N+1 查询修复" | — | API P95 < 500ms |
| **W3** | Nginx 调优 | "调整 worker_processes、keepalive、buffer_size、gzip 压缩" | — | 并发 100 请求正常 |
| **W4** | 告警策略配置 | "Prometheus AlertManager：CPU>80%、内存>90%、API错误率>5% 时钉钉告警" | `deploy/monitoring/alert_rules.yml` | 模拟触发收到告警 |

#### Day 7 — 稳定性 + Docker 化

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | 24h 稳定性测试 | "启动 Agent 压力测试脚本：每分钟 10 条消息，持续运行" | `scripts/stress_test.py` | 无 OOM / 无崩溃 / 无内存泄漏 |
| **W2** | Docker Compose 编排 | "编写运行模式的 docker-compose.yml：CRM后端+Redis+前端 Nginx 托管" | `deploy/docker/docker-compose.yml` | `docker compose up` 一键启动 |
| **W3** | 钉钉最终联调 | 全部钉钉能力验收：对话、卡片、SSO、按钮回调 | — | 所有钉钉交互正常 |
| **W4** | 运维文档 v1 | "编写运维手册：启动/停止/重启/备份/恢复/扩容操作手册" | `docs/ops-manual.md` | 文档覆盖所有运维操作 |

#### Day 8 — Prompt 最终版 + 前端优化

| 机器 | 任务 | aider 自动化指令 | 产出文件 | 完成标志 |
|------|------|-----------------|---------|---------|
| **W1** | Prompt 最终调优 | "根据 24h 测试报告做 Prompt 最终版，固化系统提示词" | 所有 Prompt 文件 | 多模型 Judge 加权评分 ≥ 4.0 |
| **W2** | 前端打包优化 | "Vite 生产构建 + 路由懒加载 + 图片压缩" | `frontend/dist/` | 首屏加载 < 3s |
| **W3** | 异常场景全覆盖 | 测试：网络断开、vLLM 超时、DB 宕机 → 系统均有友好响应 | — | 所有异常场景有兜底 |
| **W4** | 备份恢复演练 | PG 备份 → 删除数据 → 恢复 → 验证完整性 | — | 恢复后数据完整 |

#### Day 9 — 最终联调

| 窗口 | 任务 | 完成标志 |
|------|------|---------|
| **W1-W4** | 一期全功能验收联调 | 06-§4.1 的 7 项验收标准逐一验证通过 |
| **W5** | 最终评估报告 | 300+ 测试用例，E2E 全部通过 |

#### Day 10 — 上线切换

| 窗口 | 任务 | Copilot 指令示例 | 完成标志 |
|------|------|-----------------|---------|
| **W1** | Agent 引擎切换运行模式 | "从 uvicorn --reload 切换到 gunicorn + systemd 托管" | 服务稳定运行 |
| **W2** | CRM 后端切换运行模式 | "从 dev server 切换到 Docker Compose + Nginx 静态托管" | `docker compose up -d` 正常 |
| **W3** | Nginx 完整生产配置 | SSL + 限流 + 安全头 + gzip 全部生效 | 安全检查通过 |
| **W4** | 监控 + 告警全部上线 | Prometheus + Grafana + AlertManager 常驻运行 | 面板数据正常 |
| **全员** | 🎉 **一期上线** | 从开发模式正式切换到运行模式 (04-§12.7) | ✅ 里程碑"一期上线"通过 |

### 4.3 Sprint 7-8 交付物清单

| # | 交付物 | 窗口 | 关键文件 |
|---|--------|------|---------|
| D1 | 行为分析 Agent (云端) | W1 | `agent/agents/behavior_analysis.py` |
| D2 | 全量 Prompt 最终版 | W1 | `agent/prompts/` |
| D3 | Agent 降级逻辑 | W1 | `agent/middleware/fallback.py` |
| D4 | Vue3 看板 6 页 | W2 | `frontend/src/views/` |
| D5 | Docker Compose 编排 | W2 | `deploy/docker/docker-compose.yml` |
| D6 | 完整 Nginx 配置 | W3 | `deploy/nginx/` |
| D7 | Prometheus + Grafana | W4 | `deploy/monitoring/` |
| D8 | PG 流复制 | W4 | `deploy/pg/` |
| D9 | 运维手册 | W4 | `docs/ops-manual.md` |
| D10 | 300+ 测试用例 | W5 | `tests/` |
| D11 | 最终评估报告 | W5 | `reports/eval_final.json` |

### 4.4 一期总交付汇总

```
┌─────────────────────────────────────────────────────────┐
│              一期交付汇总 (Sprint 1-8)                    │
│                                                          │
│  Agent     6 个  Supervisor, 销售助手, 线索评分☁️,        │
│                  客户洞察, 商机预测, 行为分析☁️            │
│                                                          │
│  CRM Tool  11个  线索×3, 客户×3, 商机×3, 活动×2          │
│                                                          │
│  REST API  4 组  线索/客户/商机/活动 CRUD + 统计          │
│                                                          │
│  Vue3 页面 6 个  仪表盘, 线索列表, 客户详情,              │
│                  商机看板, 活动列表, 漏斗图               │
│                                                          │
│  钉钉能力  4 项  机器人对话, 互动卡片, SSO, 组织同步      │
│                                                          │
│  测试用例  300+  E2E 自动化, Agent 评估, 性能基线         │
│                                                          │
│  DB 表     ~12张 业务×8 + Agent日志 + 审计 + 用户 + 向量  │
│                                                          │
│  基础设施  vLLM(常驻), PG(主从), Redis, Nginx(SSL),       │
│           Prometheus+Grafana, Docker Compose              │
│                                                          │
│  ☁️ = 使用云端大模型 API（脱敏后调用）                    │
└─────────────────────────────────────────────────────────┘
```
