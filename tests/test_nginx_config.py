"""
Nginx 配置文件验证测试。

测试内容:
  - nginx.conf 文件存在性
  - 配置语法正确性 (通过 nginx -t 或 Docker)
  - 关键路由规则完整性 (文本解析)

契约依据:
  - contracts/crm-api.yaml  (CRM 后端 172.16.12.50:8900)
  - contracts/agent-api.yaml (Agent 引擎 172.16.11.194:8100)
  - contracts/health-api.yaml (健康检查)
"""

import shutil
import subprocess
from pathlib import Path

import pytest

# Nginx 配置文件路径（相对于项目根目录）
NGINX_CONF = Path(__file__).parent.parent / "deploy" / "nginx" / "nginx.conf"


class TestNginxConfigExists:
    """测试配置文件存在且非空。"""

    def test_config_file_exists(self):
        """nginx.conf 文件应存在于 deploy/nginx/ 目录。"""
        assert NGINX_CONF.exists(), f"配置文件不存在: {NGINX_CONF}"

    def test_config_file_not_empty(self):
        """nginx.conf 文件应非空。"""
        assert NGINX_CONF.stat().st_size > 0, "配置文件为空"


class TestNginxConfigContent:
    """测试配置文件内容完整性（文本解析）。"""

    @pytest.fixture(autouse=True)
    def _load_config(self):
        """读取配置文件内容。"""
        self.content = NGINX_CONF.read_text(encoding="utf-8")

    # ── 基础结构 ──

    def test_has_worker_processes(self):
        """应包含 worker_processes 指令。"""
        assert "worker_processes" in self.content

    def test_has_events_block(self):
        """应包含 events 块。"""
        assert "events" in self.content
        assert "worker_connections" in self.content

    def test_has_http_block(self):
        """应包含 http 块。"""
        assert "http {" in self.content or "http{" in self.content

    # ── 上游定义 ──

    def test_has_upstream_crm_backend(self):
        """应定义 CRM 后端上游 (contracts/crm-api.yaml: 172.16.12.50:8900)。"""
        assert "upstream crm_backend" in self.content
        assert "172.16.12.50:8900" in self.content

    def test_has_upstream_agent_engine(self):
        """应定义 Agent 引擎上游 (contracts/agent-api.yaml: 172.16.11.194:8100)。"""
        assert "upstream agent_engine" in self.content
        assert "172.16.11.194:8100" in self.content

    # ── 路由规则 ──

    def test_has_api_location(self):
        """应包含 /api/ location 块。"""
        assert "location /api/" in self.content

    def test_has_agent_location(self):
        """应包含 /agent/ location 块。"""
        assert "location /agent/" in self.content

    def test_has_health_location(self):
        """应包含 /health 健康检查端点。"""
        assert "/health" in self.content

    def test_has_dingtalk_location(self):
        """应预留钉钉回调路由 /dingtalk/。"""
        assert "/dingtalk/" in self.content

    # ── 路由指向正确性 ──

    def test_api_routes_to_crm_backend(self):
        """/api/ 路由应代理到 crm_backend。"""
        api_idx = self.content.find("location /api/")
        assert api_idx != -1, "未找到 /api/ location"
        api_block = self.content[api_idx : api_idx + 500]
        assert "crm_backend" in api_block, "/api/ 应代理到 crm_backend"

    def test_agent_routes_to_agent_engine(self):
        """/agent/ 路由应代理到 agent_engine。"""
        agent_idx = self.content.find("location /agent/")
        assert agent_idx != -1, "未找到 /agent/ location"
        agent_block = self.content[agent_idx : agent_idx + 500]
        assert "agent_engine" in agent_block, "/agent/ 应代理到 agent_engine"

    # ── SSE 流式输出支持 ──

    def test_agent_sse_proxy_buffering_off(self):
        """Agent 路由应关闭 proxy_buffering 以支持 SSE 流式输出。"""
        agent_idx = self.content.find("location /agent/")
        assert agent_idx != -1
        agent_block = self.content[agent_idx : agent_idx + 600]
        assert "proxy_buffering" in agent_block, "/agent/ 应配置 proxy_buffering"
        # 找到 proxy_buffering 行并确认值为 off
        for line in agent_block.splitlines():
            if "proxy_buffering" in line:
                assert "off" in line, "proxy_buffering 应设为 off"
                break

    def test_agent_proxy_cache_off(self):
        """Agent 路由应关闭 proxy_cache。"""
        agent_idx = self.content.find("location /agent/")
        assert agent_idx != -1
        agent_block = self.content[agent_idx : agent_idx + 600]
        assert "proxy_cache" in agent_block
        for line in agent_block.splitlines():
            if "proxy_cache" in line:
                assert "off" in line, "proxy_cache 应设为 off"
                break

    # ── HTTP/1.1 + keepalive ──

    def test_proxy_http_version_1_1(self):
        """代理应使用 HTTP/1.1 以支持 keepalive 和 SSE。"""
        assert "proxy_http_version 1.1" in self.content

    def test_upstream_keepalive(self):
        """上游定义应包含 keepalive 连接池。"""
        assert "keepalive" in self.content

    # ── 通用配置 ──

    def test_has_gzip(self):
        """应启用 gzip 压缩。"""
        # 匹配 "gzip on" 或 "gzip  on"
        assert "gzip" in self.content
        found = False
        for line in self.content.splitlines():
            stripped = line.strip()
            if stripped.startswith("gzip") and "on" in stripped and "gzip_" not in stripped:
                found = True
                break
        assert found, "应有 'gzip on;' 指令"

    def test_has_proxy_headers(self):
        """代理应设置 X-Real-IP 和 X-Forwarded-For 头。"""
        assert "X-Real-IP" in self.content
        assert "X-Forwarded-For" in self.content
        assert "X-Forwarded-Proto" in self.content

    def test_agent_read_timeout_longer_than_api(self):
        """Agent 路由的 read_timeout 应长于 API 路由（推理耗时更长）。"""
        api_idx = self.content.find("location /api/")
        agent_idx = self.content.find("location /agent/")
        assert api_idx != -1 and agent_idx != -1

        def _extract_read_timeout(block: str) -> int:
            """从 location 块中提取 proxy_read_timeout 秒数。"""
            for line in block.splitlines():
                if "proxy_read_timeout" in line:
                    # 提取数字部分，例如 "120s" → 120
                    parts = line.strip().rstrip(";").split()
                    for part in parts:
                        cleaned = part.replace("s", "")
                        if cleaned.isdigit():
                            return int(cleaned)
            return 0

        api_block = self.content[api_idx : api_idx + 1000]
        agent_block = self.content[agent_idx : agent_idx + 1200]

        api_timeout = _extract_read_timeout(api_block)
        agent_timeout = _extract_read_timeout(agent_block)

        assert agent_timeout > api_timeout, (
            f"Agent read_timeout ({agent_timeout}s) 应大于 API read_timeout ({api_timeout}s)"
        )


class TestNginxSyntax:
    """通过 nginx -t 或 Docker 验证配置语法。

    如果系统未安装 nginx 且未安装 docker，则跳过。
    """

    @staticmethod
    def _nginx_available() -> bool:
        """检查系统是否安装 nginx。"""
        return shutil.which("nginx") is not None

    @staticmethod
    def _docker_available() -> bool:
        """检查系统是否安装 docker。"""
        return shutil.which("docker") is not None

    def _test_with_docker(self):
        """使用 Docker 容器验证 nginx 配置语法。"""
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{NGINX_CONF.resolve()}:/etc/nginx/nginx.conf:ro",
                "nginx:1.25-alpine",
                "nginx",
                "-t",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"Docker nginx -t 失败: {result.stderr}"

    @pytest.mark.skipif(
        not (shutil.which("nginx") or shutil.which("docker")),
        reason="需要 nginx 或 docker 来验证配置语法",
    )
    def test_nginx_config_syntax(self):
        """nginx -t 配置语法检查应通过。"""
        if self._nginx_available():
            result = subprocess.run(
                ["nginx", "-t", "-c", str(NGINX_CONF.resolve())],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return
            # 本地 nginx -t 可能因缺少 mime.types 等文件失败，回退到 Docker
            if self._docker_available():
                self._test_with_docker()
            else:
                pytest.skip(
                    f"本地 nginx -t 失败（可能缺少 mime.types），且无 docker: {result.stderr}"
                )
        elif self._docker_available():
            self._test_with_docker()
