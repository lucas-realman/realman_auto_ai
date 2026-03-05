"""Sirus AI CRM — 结构化日志配置模块

为所有服务（CRM 后端、Agent 引擎、钉钉网关、Celery Worker）提供统一的
Loguru JSON 格式日志配置。

日志写入目录: /var/log/ai-crm/
文件命名规则: {service_name}.jsonl
轮转策略: 每日轮转，保留 30 天

用法::

    from scripts.log_config import setup_logging

    # 在服务启动时调用
    setup_logging("crm")        # → /var/log/ai-crm/crm.jsonl
    setup_logging("agent")      # → /var/log/ai-crm/agent.jsonl
    setup_logging("gateway")    # → /var/log/ai-crm/gateway.jsonl
    setup_logging("celery")     # → /var/log/ai-crm/celery.jsonl

    from loguru import logger
    logger.info("服务启动", extra_field="value")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

# ── 默认配置 ──────────────────────────────────────────────

DEFAULT_LOG_DIR = "/var/log/ai-crm"
DEFAULT_ROTATION = "00:00"          # 每日午夜轮转
DEFAULT_RETENTION = "30 days"       # 保留 30 天
DEFAULT_LEVEL = "INFO"
DEFAULT_ENCODING = "utf-8"
DEFAULT_ENQUEUE = True              # 异步写入，线程安全
DEFAULT_BACKTRACE = True
DEFAULT_DIAGNOSE = False            # 生产环境关闭变量诊断（防止泄漏敏感信息）


def _json_serializer(record: Dict[str, Any]) -> str:
    """将 loguru record 序列化为单行 JSON 字符串。

    输出字段:
        - timestamp: ISO 8601 时间戳
        - level:     日志级别（大写）
        - service:   服务名称
        - message:   日志消息
        - module:    模块名
        - function:  函数名
        - line:      行号
        - process_id: 进程 ID
        - thread_id:  线程 ID
        - extra:     所有额外字段（通过 logger.bind() 或 extra= 传入）
        - exception: 异常信息（如有）
    """
    import json as _json

    subset: Dict[str, Any] = {
        "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
        "level": record["level"].name,
        "service": record["extra"].get("service", "unknown"),
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "process_id": record["process"].id,
        "thread_id": record["thread"].id,
    }

    # 收集 extra 字段（排除内部使用的 service 键）
    extra = {
        k: v
        for k, v in record["extra"].items()
        if k != "service"
    }
    if extra:
        subset["extra"] = extra

    # 异常信息
    if record["exception"] is not None:
        exc = record["exception"]
        subset["exception"] = {
            "type": exc.type.__name__ if exc.type else None,
            "value": str(exc.value) if exc.value else None,
            "traceback": (
                "".join(
                    __import__("traceback").format_exception(
                        exc.type, exc.value, exc.traceback
                    )
                )
                if exc.traceback
                else None
            ),
        }

    return _json.dumps(subset, ensure_ascii=False, default=str)


def _json_sink_format(message: Any) -> str:
    """loguru format 函数，返回 JSON 行 + 换行符。"""
    return _json_serializer(message.record) + "\n"


def setup_logging(
    service_name: str,
    *,
    log_dir: Optional[str] = None,
    level: Optional[str] = None,
    rotation: Optional[str] = None,
    retention: Optional[str] = None,
    console: bool = True,
    console_json: bool = False,
) -> int:
    """为指定服务配置 Loguru 结构化日志。

    Parameters
    ----------
    service_name:
        服务名称，用于日志文件名和 JSON 中的 ``service`` 字段。
        例如: ``"crm"``, ``"agent"``, ``"gateway"``, ``"celery"``。
    log_dir:
        日志目录路径。默认 ``/var/log/ai-crm``。
        可通过环境变量 ``AI_CRM_LOG_DIR`` 覆盖。
    level:
        日志级别。默认 ``INFO``。
        可通过环境变量 ``AI_CRM_LOG_LEVEL`` 覆盖。
    rotation:
        轮转策略。默认 ``"00:00"``（每日午夜）。
    retention:
        保留策略。默认 ``"30 days"``。
    console:
        是否同时输出到 stderr（开发调试用）。默认 ``True``。
    console_json:
        控制台输出是否也用 JSON 格式。默认 ``False``（用人类可读格式）。

    Returns
    -------
    int
        loguru 文件 sink 的 handler id，可用于后续 ``logger.remove(handler_id)``。

    Raises
    ------
    OSError
        日志目录不存在且无法自动创建时抛出。

    Examples
    --------
    >>> handler_id = setup_logging("crm")  # doctest: +SKIP
    >>> logger.info("CRM 服务启动")         # doctest: +SKIP
    """
    # ── 解析配置（环境变量 > 参数 > 默认值）──
    resolved_dir = log_dir or os.environ.get("AI_CRM_LOG_DIR", DEFAULT_LOG_DIR)
    resolved_level = level or os.environ.get("AI_CRM_LOG_LEVEL", DEFAULT_LEVEL)
    resolved_rotation = rotation or DEFAULT_ROTATION
    resolved_retention = retention or DEFAULT_RETENTION

    # ── 确保日志目录存在 ──
    log_path = Path(resolved_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(
            f"无法创建日志目录 {resolved_dir}: {exc}. "
            f"请运行 scripts/setup_log_dir.sh 或手动创建并赋权。"
        ) from exc

    # ── 清除默认 handler ──
    logger.remove()

    # ── 绑定 service 名到全局 extra ──
    logger.configure(extra={"service": service_name})

    # ── 文件 sink（JSON 格式）──
    log_file = log_path / f"{service_name}.jsonl"
    handler_id = logger.add(
        str(log_file),
        format=_json_sink_format,
        level=resolved_level.upper(),
        rotation=resolved_rotation,
        retention=resolved_retention,
        encoding=DEFAULT_ENCODING,
        enqueue=DEFAULT_ENQUEUE,
        backtrace=DEFAULT_BACKTRACE,
        diagnose=DEFAULT_DIAGNOSE,
        serialize=False,  # 我们自己处理序列化
    )

    # ── 控制台 sink（可选）──
    if console:
        if console_json:
            logger.add(
                sys.stderr,
                format=_json_sink_format,
                level=resolved_level.upper(),
                enqueue=False,
                colorize=False,
            )
        else:
            logger.add(
                sys.stderr,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{extra[service]}</cyan> | "
                    "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                ),
                level=resolved_level.upper(),
                enqueue=False,
                colorize=True,
            )

    logger.info(
        "日志系统初始化完成",
        service=service_name,
        log_file=str(log_file),
        level=resolved_level,
        rotation=resolved_rotation,
        retention=resolved_retention,
    )

    return handler_id


def get_log_file_path(service_name: str, log_dir: Optional[str] = None) -> Path:
    """获取指定服务的日志文件路径。

    Parameters
    ----------
    service_name:
        服务名称。
    log_dir:
        日志目录。默认读取环境变量或使用 ``/var/log/ai-crm``。

    Returns
    -------
    Path
        日志文件的完整路径。
    """
    resolved_dir = log_dir or os.environ.get("AI_CRM_LOG_DIR", DEFAULT_LOG_DIR)
    return Path(resolved_dir) / f"{service_name}.jsonl"
