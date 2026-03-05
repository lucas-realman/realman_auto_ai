"""Alembic 迁移环境配置。

支持离线和在线两种迁移模式。
在线模式下，从 crm.config.settings 动态读取数据库 URL。
"""

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from crm.config import settings
from crm.models.base import Base

# Alembic Config 对象
config = context.config

# 配置 Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置 target_metadata 用于 autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式迁移。

    在此模式下，仅配置 URL 而不创建 Engine。
    适用于无法连接数据库的环境（如 CI/CD）。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """在线模式迁移。

    创建 Engine 并执行迁移。
    从 crm.config.settings 动态读取数据库 URL。
    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.DATABASE_URL

    connectable = create_async_engine(
        configuration["sqlalchemy.url"],
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移脚本。"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


# 根据模式选择执行方式
if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
