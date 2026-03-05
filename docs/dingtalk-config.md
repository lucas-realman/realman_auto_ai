# 钉钉企业应用注册与配置指南

> **任务**: S2_W3 — 钉钉企业应用注册
> **目标**: 在钉钉开放平台注册企业内部应用，获取 AppKey / AppSecret
> **验收标准**: 获得 AppKey + AppSecret，并完成基础配置

---

## 1. 前置条件

- 拥有钉钉企业管理员权限（或由管理员协助操作）
- 企业已完成钉钉组织认证
- 准备好回调地址（Gateway 服务器公网 IP 或域名）

---

## 2. 注册步骤

### 2.1 登录钉钉开放平台

1. 浏览器访问 [钉钉开放平台](https://open-dev.dingtalk.com/)
2. 使用企业管理员账号扫码登录
3. 进入「应用开发」→「企业内部开发」

### 2.2 创建企业内部应用

1. 点击「创建应用」
2. 填写应用信息：
   - **应用名称**: `睿尔曼智能 CRM`
   - **应用描述**: `AI-Native 智能 CRM 系统，支持线索管理、客户管理、商机跟踪、AI 洞察`
   - **应用图标**: 上传公司 Logo（建议 512×512 PNG）
3. 点击「确认创建」

### 2.3 获取凭证

创建成功后，在应用详情页的「凭证与基础信息」中获取：

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| **AppKey** (Client ID) | 应用唯一标识 | `dingxxxxxxxxxxxxxxxx` |
| **AppSecret** (Client Secret) | 应用密钥（**严禁泄露**） | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |
| **AgentId** | 企业内部应用 AgentId | `xxxxxxxxxx` |

> ⚠️ **安全提醒**: AppSecret 仅在创建时显示一次，请立即保存到安全位置。
> 生产环境中应通过环境变量注入，**禁止**硬编码到代码中。

### 2.4 配置机器人能力

1. 在应用详情页，进入「添加能力」
2. 添加「机器人」能力
3. 配置机器人：
   - **消息接收模式**: `HTTP 模式`
   - **消息接收地址**: `https://<GATEWAY_DOMAIN>/dingtalk/callback`
     - 开发环境: `http://<GATEWAY_IP>:8080/dingtalk/callback`
   - **支持的消息类型**: 勾选「文本消息」「富文本消息」

### 2.5 配置权限

在「权限管理」中申请以下权限：

| 权限名称 | 权限码 | 用途 |
|----------|--------|------|
| 企业内机器人发送消息 | `qyapi_robot_sendmsg` | Agent 回复消息 |
| 通讯录个人信息读权限 | `Contact.User.Read` | SSO 获取用户信息 |
| 通讯录部门信息读权限 | `Contact.Department.Read` | 组织架构同步 |
| 获取用户 userid | `Contact.User.mobile` | 手机号关联 |
| 互动卡片高级权限 | `InteractiveCard` | 发送互动卡片 |

### 2.6 配置免登（SSO）

1. 进入「登录与分享」
2. 配置「免登」：
   - **回调域名**: `<GATEWAY_DOMAIN>`（不含协议和端口）
3. 记录 **SSOSecret**（如有单独提供）

### 2.7 配置事件订阅（可选，Sprint 3-4 使用）

1. 进入「事件与回调」
2. 配置：
   - **请求网址**: `https://<GATEWAY_DOMAIN>/dingtalk/event`
   - **Token**: 自定义随机字符串（用于验签）
   - **AES Key**: 自定义 43 位随机字符串（用于加解密）
3. 订阅事件：
   - `user_add_org` — 用户加入组织
   - `user_leave_org` — 用户离开组织

---

## 3. 环境变量配置

获取凭证后，在各服务器上配置环境变量：

```bash
# Gateway 服务器 (deploy/dingtalk/)
export DINGTALK_APP_KEY="dingxxxxxxxxxxxxxxxx"
export DINGTALK_APP_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export DINGTALK_AGENT_ID="xxxxxxxxxx"
export DINGTALK_ROBOT_CODE="dingxxxxxxxxxxxxxxxx"

# 回调验签配置
export DINGTALK_CALLBACK_TOKEN="your_random_token_string"
export DINGTALK_CALLBACK_AES_KEY="your_43_char_random_aes_key_string_here_xx"

# SSO 配置
export DINGTALK_SSO_SECRET="your_sso_secret_if_applicable"
```

也可以使用 `.env` 文件（已在 `.gitignore` 中排除）：

```ini
# deploy/dingtalk/.env
DINGTALK_APP_KEY=dingxxxxxxxxxxxxxxxx
DINGTALK_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DINGTALK_AGENT_ID=xxxxxxxxxx
DINGTALK_ROBOT_CODE=dingxxxxxxxxxxxxxxxx
DINGTALK_CALLBACK_TOKEN=your_random_token_string
DINGTALK_CALLBACK_AES_KEY=your_43_char_random_aes_key_string_here_xx
```

---

## 4. 验证清单

完成注册后，逐项确认：

- [ ] AppKey 已获取并安全保存
- [ ] AppSecret 已获取并安全保存
- [ ] AgentId 已记录
- [ ] 机器人能力已添加
- [ ] 消息接收地址已配置（开发环境可暂用 HTTP）
- [ ] 所需权限已申请并通过审批
- [ ] 环境变量已配置到 Gateway 服务器
- [ ] `.env` 文件已添加到 `.gitignore`

---

## 5. 常见问题

### Q: AppSecret 忘记保存怎么办？

A: 在应用详情页点击「重置」可以重新生成，但旧的 Secret 会立即失效。

### Q: 回调地址必须是 HTTPS 吗？

A: 生产环境必须 HTTPS。开发阶段可以使用 HTTP，但钉钉部分功能（如互动卡片回调）可能要求 HTTPS。

### Q: 权限申请需要审批吗？

A: 企业内部应用的权限通常自动通过。如果组织设置了审批流程，需要管理员审批。

### Q: 如何测试机器人是否配置成功？

A: 在钉钉中搜索应用名称，发送一条消息。如果 Gateway 服务器日志中能看到回调请求，说明配置成功。

---

## 6. 网络架构参考

```
钉钉用户
  │
  ▼ (公网 HTTPS)
Gateway (Nginx)  ─── /dingtalk/callback ──→ deploy/dingtalk/ (Bot 服务)
  │                                              │
  │                                              ▼
  ├── /agent/* ──→ 4090:8100 (Agent 引擎)       Redis (会话)
  │                    │
  │                    ▼
  │               vLLM localhost:8000
  │
  └── /api/*  ──→ mac_min_8T:8900 (CRM 后端)
                       │
                       ▼
                  PostgreSQL + Redis
```

---

## 7. 相关文档

- [钉钉开放平台文档](https://open.dingtalk.com/document/)
- [企业内部应用开发指南](https://open.dingtalk.com/document/orgapp/overview)
- [机器人消息回调](https://open.dingtalk.com/document/orgapp/receive-message)
- [互动卡片开发](https://open.dingtalk.com/document/orgapp/interactive-card-overview)
- 项目接口契约: `contracts/agent-api.yaml`, `contracts/crm-api.yaml`
