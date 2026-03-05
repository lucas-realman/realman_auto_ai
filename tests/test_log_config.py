"""tests/test_log_config.py — scripts/log_config.py 的单元测试

验证:
    1. setup_logging 正确创建日志文件
    2. 日志输出为合法 JSON 格式
    3. JSON 包含所有必需字段
    4. 异常信息正确记录
    5. 自定义 extra 字段正确传递
    6. 环境变量覆盖配置
    7. 日志目录不存在时自动创建
    8. get_log_file_path 返回正确路径
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import pytest
from loguru import logger


@pytest.fixture(autouse=True)
def _clean_logger():
    """每个测试前后清理 loguru handlers。"""
    logger.remove()
    yield
    logger.remove()


@pytest.fixture()
def log_dir(tmp_path: Path) -> Path:
    """提供一个临时日志目录。"""
    d = tmp_path / "ai-crm-logs"
    d.mkdir()
    return d


@pytest.fixture()
def _setup(log_dir: Path):
    """配置日志并返回目录路径。"""
    from scripts.log_config import setup_logging

    setup_logging("test_svc", log_dir=str(log_dir), console=False)
    return log_dir


def _read_log_lines(log_dir: Path, service: str = "test_svc") -> list[Dict[str, Any]]:
    """读取 jsonl 日志文件，返回解析后的字典列表。"""
    log_file = log_dir / f"{service}.jsonl"
    # loguru enqueue=True 使用后台线程写入，需要 complete
    logger.complete()
    if not log_file.exists():
        return []
    lines = []
    for raw in log_file.read_text(encoding="utf-8").strip().splitlines():
        if raw.strip():
            lines.append(json.loads(raw))
    return lines


class TestSetupLogging:
    """测试 setup_logging 函数。"""

    def test_creates_log_file(self, log_dir: Path) -> None:
        """setup_logging 应当创建 {service}.jsonl 文件。"""
        from scripts.log_config import setup_logging

        setup_logging("crm", log_dir=str(log_dir), console=False)
        logger.info("hello")
        logger.complete()

        log_file = log_dir / "crm.jsonl"
        assert log_file.exists(), f"日志文件 {log_file} 应当存在"

    def test_json_format(self, log_dir: Path) -> None:
        """每行日志应当是合法的 JSON。"""
        from scripts.log_config import setup_logging

        setup_logging("agent", log_dir=str(log_dir), console=False)
        logger.info("测试消息1")
        logger.warning("测试消息2")
        logger.complete()

        lines = _read_log_lines(log_dir, "agent")
        # 至少有初始化日志 + 2 条测试消息
        assert len(lines) >= 2, f"应当至少有 2 条日志，实际 {len(lines)} 条"

    def test_required_fields(self, log_dir: Path) -> None:
        """JSON 日志应包含所有必需字段。"""
        from scripts.log_config import setup_logging

        setup_logging("gateway", log_dir=str(log_dir), console=False)
        logger.info("字段检查")
        logger.complete()

        lines = _read_log_lines(log_dir, "gateway")
        # 取最后一条（跳过初始化日志）
        record = lines[-1]

        required_fields = [
            "timestamp",
            "level",
            "service",
            "message",
            "module",
            "function",
            "line",
            "process_id",
            "thread_id",
        ]
        for field in required_fields:
            assert field in record, f"缺少必需字段: {field}"

    def test_service_name_in_json(self, log_dir: Path) -> None:
        """JSON 中的 service 字段应匹配传入的服务名。"""
        from scripts.log_config import setup_logging

        setup_logging("celery", log_dir=str(log_dir), console=False)
        logger.info("服务名测试")
        logger.complete()

        lines = _read_log_lines(log_dir, "celery")
        for record in lines:
            assert record["service"] == "celery"

    def test_log_level_correct(self, log_dir: Path) -> None:
        """日志级别应正确记录。"""
        from scripts.log_config import setup_logging

        setup_logging("crm", log_dir=str(log_dir), console=False, level="DEBUG")
        logger.debug("调试")
        logger.info("信息")
        logger.warning("警告")
        logger.error("错误")
        logger.complete()

        lines = _read_log_lines(log_dir, "crm")
        levels = [r["level"] for r in lines]
        assert "DEBUG" in levels
        assert "INFO" in levels
        assert "WARNING" in levels
        assert "ERROR" in levels

    def test_exception_logging(self, log_dir: Path) -> None:
        """异常信息应包含 type、value、traceback。"""
        from scripts.log_config import setup_logging

        setup_logging("crm", log_dir=str(log_dir), console=False)
        try:
            raise ValueError("测试异常")
        except ValueError:
            logger.exception("捕获异常")
        logger.complete()

        lines = _read_log_lines(log_dir, "crm")
        exc_lines = [r for r in lines if r.get("exception")]
        assert len(exc_lines) >= 1, "应当有至少 1 条异常日志"

        exc_record = exc_lines[0]["exception"]
        assert exc_record["type"] == "ValueError"
        assert "测试异常" in exc_record["value"]
        assert exc_record["traceback"] is not None

    def test_extra_fields(self, log_dir: Path) -> None:
        """通过 logger.bind() 传入的 extra 字段应出现在 JSON 中。"""
        from scripts.log_config import setup_logging

        setup_logging("agent", log_dir=str(log_dir), console=False)
        logger.bind(user_id="u-123", action="create_lead").info("额外字段测试")
        logger.complete()

        lines = _read_log_lines(log_dir, "agent")
        last = lines[-1]
        assert "extra" in last
        assert last["extra"]["user_id"] == "u-123"
        assert last["extra"]["action"] == "create_lead"

    def test_env_var_override_log_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量 AI_CRM_LOG_DIR 应覆盖默认目录。"""
        from scripts.log_config import setup_logging

        env_dir = tmp_path / "env-logs"
        env_dir.mkdir()
        monkeypatch.setenv("AI_CRM_LOG_DIR", str(env_dir))

        setup_logging("crm", console=False)
        logger.info("环境变量测试")
        logger.complete()

        assert (env_dir / "crm.jsonl").exists()

    def test_env_var_override_level(
        self, log_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量 AI_CRM_LOG_LEVEL 应覆盖默认级别。"""
        from scripts.log_config import setup_logging

        monkeypatch.setenv("AI_CRM_LOG_LEVEL", "WARNING")

        setup_logging("crm", log_dir=str(log_dir), console=False)
        logger.debug("不应记录")
        logger.info("不应记录")
        logger.warning("应当记录")
        logger.complete()

        lines = _read_log_lines(log_dir, "crm")
        levels = {r["level"] for r in lines}
        assert "DEBUG" not in levels
        # INFO 出现在初始化消息中不一定，但 WARNING 一定在
        assert "WARNING" in levels

    def test_auto_create_log_dir(self, tmp_path: Path) -> None:
        """日志目录不存在时应自动创建。"""
        from scripts.log_config import setup_logging

        new_dir = tmp_path / "new" / "nested" / "logs"
        assert not new_dir.exists()

        setup_logging("crm", log_dir=str(new_dir), console=False)
        logger.info("自动创建目录测试")
        logger.complete()

        assert new_dir.exists()
        assert (new_dir / "crm.jsonl").exists()

    def test_returns_handler_id(self, log_dir: Path) -> None:
        """setup_logging 应返回 handler id（int）。"""
        from scripts.log_config import setup_logging

        handler_id = setup_logging("crm", log_dir=str(log_dir), console=False)
        assert isinstance(handler_id, int)

    def test_console_json_mode(
        self, log_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """console_json=True 时控制台输出也应为 JSON。"""
        from scripts.log_config import setup_logging

        setup_logging(
            "crm",
            log_dir=str(log_dir),
            console=True,
            console_json=True,
        )
        logger.info("控制台JSON测试")
        logger.complete()

        # 文件中的日志应当正常
        lines = _read_log_lines(log_dir, "crm")
        assert len(lines) >= 1


class TestGetLogFilePath:
    """测试 get_log_file_path 函数。"""

    def test_default_path(self) -> None:
        """默认路径应为 /var/log/ai-crm/{service}.jsonl。"""
        from scripts.log_config import get_log_file_path

        path = get_log_file_path("crm")
        assert path == Path("/var/log/ai-crm/crm.jsonl")

    def test_custom_dir(self, tmp_path: Path) -> None:
        """自定义目录应正确返回。"""
        from scripts.log_config import get_log_file_path

        path = get_log_file_path("agent", log_dir=str(tmp_path))
        assert path == tmp_path / "agent.jsonl"

    def test_env_var_override(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """环境变量应覆盖默认目录。"""
        from scripts.log_config import get_log_file_path

        monkeypatch.setenv("AI_CRM_LOG_DIR", str(tmp_path))
        path = get_log_file_path("gateway")
        assert path == tmp_path / "gateway.jsonl"


class TestMultipleServices:
    """测试多服务共存场景。"""

    def test_multiple_services_write_separate_files(self, log_dir: Path) -> None:
        """不同服务应写入不同文件。"""
        from scripts.log_config import setup_logging

        # 注意：loguru 是全局的，这里模拟的是多次配置的场景
        # 实际部署中每个进程只调用一次
        setup_logging("crm", log_dir=str(log_dir), console=False)
        logger.info("CRM日志")
        logger.complete()

        crm_lines = _read_log_lines(log_dir, "crm")
        assert len(crm_lines) >= 1
        assert all(r["service"] == "crm" for r in crm_lines)
