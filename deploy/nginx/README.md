# Nginx 网关配置

## 概述

Sirus AI CRM 网关层 Nginx 配置，负责将外部请求路由到内网各服务节点。

## 路由规则

| 路径 | 上游服务 | 说明 |
|------|---------|------|
| `/api/*` | `172.16.12.50:8900` (CRM 后端) | 线索/客户/商机/活动 CRUD + 统计 |
| `/agent/*` | `172.16.11.194:8100` (Agent 引擎) | 对话、流式输出、评估 |
| `/dingtalk/*` | `172.16.12.50:8900` (CRM 后端) | 钉钉回调（预留） |
| `/health` | 网关本地 | 网关健康检查 |

## 验证

```bash
# 语法检查
nginx -t -c /path/to/deploy/nginx/nginx.conf

# 或使用 Docker 验证（无需本地安装 nginx）
docker run --rm -v $(pwd)/deploy/nginx/nginx.conf:/etc/nginx/nginx.conf:ro nginx:1.25-alpine nginx -t
```

## 部署

```bash
# 复制配置到 nginx 默认路径
sudo cp deploy/nginx/nginx.conf /etc/nginx/nginx.conf

# 检查语法
sudo nginx -t

# 重载配置
sudo nginx -s reload
```
