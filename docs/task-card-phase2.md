# Sprint 3 — 可视化交互层
# 状态: 待执行 | 批次: visual-batch-002

## 前置条件（本地已完成）

- [x] CRM Bug 全量修复（24 处），已提交
- [x] main.py 自动建表 + CORS + uuid-ossp 扩展

## 任务分配

| # | 机器 | SSH 别名 | 任务 | 目标目录 | 预计时间 |
|---|------|---------|------|---------|---------|
| T5 | mac_min_8T | ssh mac_min_8T | PostgreSQL/Redis 搭建 + API 验证 | (运维) | 10 min |
| T6 | 4090 | ssh 4090 | Web 管理看板 (React + Ant Design) | dashboard/ | 20 min |
| T7 | gateway | ssh gateway | 钉钉机器人集成 + 互动卡片 | deploy/dingtalk/ | 20 min |

## 执行顺序

1. 先行: T5（数据库就绪后 API 才能启动）
2. 并行: T6 + T7（独立模块，可同时在不同机器执行）

---

### T5 — PostgreSQL/Redis 搭建 + API 验证 (mac_min_8T)

在 mac_min_8T 上搭建数据库并验证 CRM API 可正常启动。

**手动执行步骤:**

```bash
# 1. PostgreSQL
brew services start postgresql@14   # 或系统已有的版本
createdb ai_crm
psql ai_crm -c "CREATE USER ai_crm WITH PASSWORD 'ai_crm_2026';"
psql ai_crm -c "GRANT ALL PRIVILEGES ON DATABASE ai_crm TO ai_crm;"
psql ai_crm -c "ALTER DATABASE ai_crm OWNER TO ai_crm;"

# 2. Redis
brew services start redis

# 3. 安装依赖 + 启动 API
cd ~/ai-crm
pip install -r crm/requirements.txt
uvicorn crm.main:app --host 0.0.0.0 --port 8900 --reload

# 4. 验证
curl http://localhost:8900/health
# → {"status":"ok","service":"crm"}
# 浏览器打开 http://172.16.12.50:8900/docs → Swagger UI
```

**验收标准:**
- /health 返回 200
- Swagger UI 可访问
- POST /api/v1/leads/ 可创建线索

---

### T6 — Web 管理看板 (4090 → dashboard/)

在 `dashboard/` 目录下创建轻量级 React + Ant Design 管理看板。

**必须生成的文件:**
- `dashboard/package.json` — React 18 + Vite + Ant Design 5 + axios + @ant-design/charts
- `dashboard/vite.config.ts` — 开发代理: /api → http://172.16.12.50:8900
- `dashboard/tsconfig.json`
- `dashboard/index.html`
- `dashboard/src/main.tsx` — ReactDOM.createRoot 入口
- `dashboard/src/App.tsx` — ProLayout 布局 + React Router，侧边栏: 线索管理 / 客户管理 / 商机管道 / 活动记录
- `dashboard/src/api/client.ts` — axios 实例，baseURL=/api/v1，全局错误处理
- `dashboard/src/api/leads.ts` — fetchLeads, createLead, updateLead, convertLead
- `dashboard/src/api/customers.ts` — fetchCustomers, createCustomer, getCustomerDetail
- `dashboard/src/api/opportunities.ts` — fetchOpportunities, createOpportunity, updateOpportunity
- `dashboard/src/api/activities.ts` — fetchActivities, createActivity
- `dashboard/src/pages/LeadsPage.tsx` — 线索看板：ProTable 列表 + 状态筛选 + 新建弹窗 + 转化按钮
- `dashboard/src/pages/CustomersPage.tsx` — 客户列表：ProTable + 等级筛选 + 点击查看 360° 视图
- `dashboard/src/pages/OpportunitiesPage.tsx` — 商机管道：Kanban 看板视图（按 stage 分列）+ 拖拽推进
- `dashboard/src/pages/ActivitiesPage.tsx` — 活动时间线：Timeline 组件 + 新建活动表单
- `dashboard/src/pages/DashboardHome.tsx` — 首页概览：4 个统计卡片 (total leads/customers/opportunities/activities) + 商机漏斗图 + 最近活动

**关键约束:**
- 使用 Ant Design 5 ProComponents (ProTable, ProForm) 减少代码量
- 所有 API 请求走 /api/v1/ 前缀，开发时 Vite proxy 转发
- 响应式布局，支持中文界面
- 颜色主题: 蓝色系 (#1677ff)
- 表格支持分页，默认 20 条/页
- 所有字段使用 camelCase（匹配后端 CamelModel 别名输出）

---

### T7 — 钉钉机器人集成 (gateway → deploy/dingtalk/)

升级现有 `deploy/dingtalk/stub_server.py` 为完整钉钉机器人集成。

**必须生成/修改的文件:**
- `deploy/dingtalk/bot_server.py` — 替代 stub_server.py，完整钉钉机器人服务 (FastAPI, port 9000):
  - `POST /dingtalk/callback` — 接收钉钉 outgoing 消息
  - 解析消息内容 → 调用 Agent /agent/chat (http://172.16.11.194:8100/agent/chat)
  - 将 Agent 回复格式化为钉钉消息（Markdown 或互动卡片 JSON）
  - 支持 DingTalk 签名验证 (HmacSHA256)
  - `POST /dingtalk/interactive` — 接收互动卡片回调
  - `GET /health` — 健康检查
- `deploy/dingtalk/card_templates.py` — 互动卡片模板:
  - lead_card: 线索信息卡片（显示线索详情 + 转化/跟进按钮）
  - customer_card: 客户 360° 视图卡片
  - opportunity_card: 商机卡片（显示阶段推进按钮）
  - confirm_card: 操作确认卡片
- `deploy/dingtalk/message_parser.py` — 消息解析器:
  - 从钉钉消息中提取意图和参数
  - 支持常见命令: "查线索 XX公司" / "新建线索" / "客户详情 XX" / "推进商机"
- `deploy/dingtalk/dingtalk_client.py` — 钉钉 API 客户端:
  - 获取 access_token (AppKey + AppSecret)
  - 发送消息到群或个人
  - 更新互动卡片
- `deploy/dingtalk/config.py` — 配置:
  - AGENT_URL (default http://172.16.11.194:8100)
  - CRM_URL (default http://172.16.12.50:8900)
  - DINGTALK_APP_KEY, DINGTALK_APP_SECRET, DINGTALK_ROBOT_CODE
  - DINGTALK_CALLBACK_TOKEN, DINGTALK_AES_KEY (签名验证用)
  - APP_PORT (default 9000)
- `deploy/dingtalk/requirements.txt` — fastapi, uvicorn, httpx, pydantic-settings, dingtalk-sdk (可选), cryptography

**关键约束:**
- 签名验证必须实现（安全要求）
- 互动卡片使用钉钉最新卡片 JSON 格式
- 所有外部调用使用 httpx.AsyncClient (async)
- 错误时返回友好的钉钉消息而非 500
- 配置通过环境变量注入，不硬编码密钥

---

## Nginx 更新 (gateway，附加)

T7 完成后，更新 `deploy/nginx/ai-crm.conf` 添加看板路由:

```nginx
location / {
    proxy_pass http://172.16.11.194:3000;  # dashboard dev server
}
```

## 验收 Checklist

- [ ] T5: curl /health 返回 200; Swagger UI 可操作全部 CRUD
- [ ] T6: npm run dev 启动后浏览器可访问看板; 线索列表/商机看板/客户列表正常渲染
- [ ] T7: 钉钉群发消息 → 机器人回复; 互动卡片点击按钮有响应
