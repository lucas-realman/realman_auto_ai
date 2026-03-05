# Sirus AI CRM — Nginx Docker 镜像
# 用于本地语法验证和开发测试
FROM nginx:1.25-alpine

COPY nginx.conf /etc/nginx/nginx.conf

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
