"""
数据库初始化脚本测试。

测试内容:
  - scripts/init_db.sh 文件存在且可执行
  - PostgreSQL 连接正常
  - ai_crm 数据库已创建
  - uuid-ossp 和 vector 扩展已安装
  - Redis 连接正常

契约依据:
  - contracts/db-schema.sql (数据库结构)
  - contracts/event-bus.yaml (Redis 连接)
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
INIT_SCRIPT = PROJECT_ROOT / "scripts" / "init_db.sh"

# 默认使用当前系统用户连接 PostgreSQL（macOS Homebrew 默认行为）
PG_USER = os.getenv("PGUSER", os.getenv("USER", "postgres"))


# ──────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """执行外部命令并返回结果。"""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _psql(sql: str, dbname: str = "ai_crm") -> subprocess.CompletedProcess:
    """通过 psql 执行 SQL 语句。"""
    return _run(["psql", "-U", PG_USER, "-d", dbname, "-tAc", sql])


# ──────────────────────────────────────────────
# 测试: 脚本文件
# ──────────────────────────────────────────────

class TestInitScriptFile:
    """测试初始化脚本文件存在性与权限。"""

    def test_script_exists(self):
        """scripts/init_db.sh 应存在。"""
        assert INIT_SCRIPT.exists(), f"初始化脚本不存在: {INIT_SCRIPT}"

    def test_script_not_empty(self):
        """scripts/init_db.sh 应非空。"""
        assert INIT_SCRIPT.stat().st_size > 0, "初始化脚本为空"

    def test_script_is_executable(self):
        """scripts/init_db.sh 应可执行。"""
        assert os.access(INIT_SCRIPT, os.X_OK), (
            "初始化脚本不可执行，请运行: chmod +x scripts/init_db.sh"
        )

    def test_script_has_shebang(self):
        """scripts/init_db.sh 应以 shebang 行开头。"""
        first_line = INIT_SCRIPT.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("#!"), f"缺少 shebang 行，首行为: {first_line}"

    def test_script_uses_set_e(self):
        """scripts/init_db.sh 应使用 set -e 确保出错即退出。"""
        content = INIT_SCRIPT.read_text(encoding="utf-8")
        assert "set -e" in content or "set -euo pipefail" in content, (
            "脚本缺少 set -e 或 set -euo pipefail"
        )


# ──────────────────────────────────────────────
# 测试: PostgreSQL
# ──────────────────────────────────────────────

class TestPostgreSQL:
    """测试 PostgreSQL 安装与配置。"""

    @pytest.fixture(autouse=True)
    def _require_psql(self):
        """跳过测试如果 psql 不可用。"""
        if not shutil.which("psql"):
            pytest.skip("psql 命令不可用")

    def test_postgresql_connection(self):
        """PostgreSQL 应可连接。"""
        result = _psql("SELECT 1", dbname="postgres")
        assert result.returncode == 0, f"PostgreSQL 连接失败: {result.stderr}"

    def test_ai_crm_database_exists(self):
        """ai_crm 数据库应存在。"""
        result = _run(["psql", "-U", PG_USER, "-d", "postgres", "-lqt"])
        assert result.returncode == 0, f"查询数据库列表失败: {result.stderr}"
        databases = [
            line.split("|")[0].strip()
            for line in result.stdout.splitlines()
            if "|" in line
        ]
        assert "ai_crm" in databases, (
            f"ai_crm 数据库不存在，请先运行 scripts/init_db.sh。已有数据库: {databases}"
        )

    def test_uuid_ossp_extension_installed(self):
        """ai_crm 中应安装 uuid-ossp 扩展。"""
        result = _psql("SELECT extname FROM pg_extension WHERE extname='uuid-ossp';")
        assert result.returncode == 0, f"查询扩展失败: {result.stderr}"
        assert "uuid-ossp" in result.stdout, "uuid-ossp 扩展未安装"

    def test_vector_extension_installed(self):
        """ai_crm 中应安装 vector (pgvector) 扩展。"""
        result = _psql("SELECT extname FROM pg_extension WHERE extname='vector';")
        assert result.returncode == 0, f"查询扩展失败: {result.stderr}"
        assert "vector" in result.stdout, "vector 扩展未安装"

    def test_uuid_generation_works(self):
        """uuid_generate_v4() 函数应可用。"""
        result = _psql("SELECT uuid_generate_v4();")
        assert result.returncode == 0, f"uuid_generate_v4() 执行失败: {result.stderr}"
        # UUID 格式: 8-4-4-4-12 hex digits
        uuid_val = result.stdout.strip()
        assert len(uuid_val) == 36, f"uuid_generate_v4() 返回值格式异常: {uuid_val}"


# ──────────────────────────────────────────────
# 测试: Redis
# ──────────────────────────────────────────────

class TestRedis:
    """测试 Redis 安装与配置。"""

    @pytest.fixture(autouse=True)
    def _require_redis_cli(self):
        """跳过测试如果 redis-cli 不可用。"""
        if not shutil.which("redis-cli"):
            pytest.skip("redis-cli 命令不可用")

    def test_redis_connection(self):
        """Redis 应可连接并返回 PONG。"""
        result = _run(["redis-cli", "ping"])
        assert result.returncode == 0, f"Redis 连接失败: {result.stderr}"
        assert result.stdout.strip() == "PONG", f"Redis 响应异常: {result.stdout}"

    def test_redis_set_get(self):
        """Redis SET/GET 应正常工作。"""
        key = "__sirus_crm_init_test__"
        # SET
        result_set = _run(["redis-cli", "SET", key, "ok", "EX", "5"])
        assert result_set.returncode == 0, f"Redis SET 失败: {result_set.stderr}"
        # GET
        result_get = _run(["redis-cli", "GET", key])
        assert result_get.returncode == 0, f"Redis GET 失败: {result_get.stderr}"
        assert result_get.stdout.strip() == "ok", f"Redis GET 返回值异常: {result_get.stdout}"
        # DEL
        _run(["redis-cli", "DEL", key])

    def test_redis_version_at_least_7(self):
        """Redis 版本应 >= 7（支持 Redis Stream 消费者组功能增强）。"""
        result = _run(["redis-cli", "INFO", "server"])
        assert result.returncode == 0, f"Redis INFO 失败: {result.stderr}"
        for line in result.stdout.splitlines():
            if line.startswith("redis_version:"):
                version = line.split(":")[1].strip()
                major = int(version.split(".")[0])
                assert major >= 7, f"Redis 版本 {version} < 7，请升级"
                return
        pytest.fail("未能从 Redis INFO 中获取版本号")


# ──────────────────────────────────────────────
# 测试: 验收标准
# ──────────────────────────────────────────────

class TestAcceptanceCriteria:
    """验收标准测试 — 与任务卡 Day 1 完成标志对应。"""

    def test_psql_select_1(self):
        """验收: psql -c "SELECT 1" 成功。"""
        if not shutil.which("psql"):
            pytest.skip("psql 不可用")
        result = _run(
            ["psql", "-U", PG_USER, "-d", "ai_crm", "-c", "SELECT 1"]
        )
        assert result.returncode == 0, f"psql -c 'SELECT 1' 失败: {result.stderr}"
        assert "1" in result.stdout, f"SELECT 1 未返回预期结果: {result.stdout}"

    def test_redis_cli_ping(self):
        """验收: redis-cli ping 成功。"""
        if not shutil.which("redis-cli"):
            pytest.skip("redis-cli 不可用")
        result = _run(["redis-cli", "ping"])
        assert result.returncode == 0, f"redis-cli ping 失败: {result.stderr}"
        assert result.stdout.strip() == "PONG", f"redis-cli ping 响应异常: {result.stdout}"
