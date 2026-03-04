# Sirus AI CRM — 待办任务清单

> 暂存日期: 2026-03-04
> 原因: 优先搭建自动化开发流水线，文档编写任务暂停

---

## 🔴 最高优先级（进行中）

- [ ] **搭建自动化开发流水线** — 见 08-自动化开发流水线.md

---

## 🟡 已暂停任务：文档编写

### 11-数据库设计文档（优先级高，S1 Day 2 截止）

| # | 子任务 | 状态 | 说明 |
|---|--------|------|------|
| 1 | 文档框架与设计约定 | ⬜ 未开始 | 命名规范、通用字段、数据类型约定、枚举/软删除策略 |
| 2 | 核心业务实体 DDL | ⬜ 未开始 | User/Lead/Customer/Contact/Opportunity/Activity — 含 ai_ 字段 |
| 3 | 业务流转实体 DDL | ⬜ 未开始 | Contract/Order/Payment/Target/Task/Product |
| 4 | 横切与辅助实体 DDL | ⬜ 未开始 | Ticket/Approval/Notification/Tag/Attachment |
| 5 | Agent 专属表 DDL | ⬜ 未开始 | AuditEvent/AgentLog/Knowledge/Feedback/AICache |
| 6 | 索引/约束/分区策略 | ⬜ 未开始 | 全表索引清单、FK/CHECK、AuditEvent 按月分区、HNSW |
| 7 | pgvector 与迁移方案 | ⬜ 未开始 | pgvector 扩展、HNSW 参数、Alembic 策略、docker-compose |

### 10-Agent 详细设计文档（S2 结束截止）

| # | 子任务 | 状态 | 说明 |
|---|--------|------|------|
| 1 | 框架与 Supervisor 设计 | ⬜ 未开始 | 自研框架架构图、Tool-Calling 循环、Supervisor Prompt |
| 2 | 响应型 Agent Prompt+Tool | ⬜ 未开始 | 销售助手/数据问答/合同审查 — System Prompt + 工具列表 |
| 3 | 主动型 Agent Prompt+触发 | ⬜ 未开始 | 巡检/预警/规划/催收/晨报 — Prompt + cron/事件触发 |
| 4 | 分析型 Agent Prompt+输出 | ⬜ 未开始 | 客户洞察/商机预测/漏斗分析/行为分析/线索评分 |
| 5 | Tool JSON Schema 定义 | ⬜ 未开始 | 所有 Tool 的 OpenAI Function Calling 格式定义 |
| 6 | 协作协议与模型路由 | ⬜ 未开始 | Agent 间委派消息格式、本地 vLLM vs 云端路由规则 |
| 7 | 降级与错误恢复 | ⬜ 未开始 | LLM 超时/崩溃/低置信度降级、熔断阈值、重试策略 |

### 12-钉钉集成方案文档（S2 结束截止）

| # | 子任务 | 状态 | 说明 |
|---|--------|------|------|
| 1 | Stream 模式与机器人 | ⬜ 未开始 | Stream WebSocket 对接、消息接收→Agent 分发→回复流程 |
| 2 | 互动卡片模板设计 | ⬜ 未开始 | 线索领取/商机推进/预警/审批卡片 JSON 模板 + 回调 |
| 3 | 审批流集成方案 | ⬜ 未开始 | OA 审批 API 对接、审批模板、审批事件→Agent 处理 |
| 4 | 组织同步与 SSO 认证 | ⬜ 未开始 | 通讯录同步、OAuth2 SSO、JWT 生成刷新、权限映射 |

### 13-部署方案文档（S6 结束截止）

| # | 子任务 | 状态 | 说明 |
|---|--------|------|------|
| 1 | docker-compose 编排 | ⬜ 未开始 | dev.yml (PG+Redis) + prod.yml (全组件) |
| 2 | 各节点服务与 Nginx | ⬜ 未开始 | 5 台机器服务清单、systemd、Nginx 反向代理配置 |
| 3 | 监控/备份/切换流程 | ⬜ 未开始 | Prometheus/Grafana、PG 流复制、开发→运行切换 checklist |

---

## ✅ 已完成

- [x] 风险识别与应对全量 Review（v1.6.3，14 项已解决，1 项已废弃）
