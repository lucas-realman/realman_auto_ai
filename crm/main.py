"""Sirus AI-CRM 后端入口。

启动方式:
    uvicorn crm.main:app --host 0.0.0.0 --port 8900 --reload

功能:
    - 自动建表（开发模式）
    - 注册 CORS 中间件
    - 挂载 leads / customers / opportunities / activities 路由
    - /health 端点符合 health-api.yaml 契约
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from crm import __version__
from crm.config import settings
from crm.database import engine, check_db_connection
from crm.models import Base  # noqa: F401  — ensure all models are registered
from crm.services.event_publisher import close_redis
from crm.api.leads import router as leads_router
from crm.api.customers import router as customers_router
from crm.api.opportunities import router as opportunities_router
from crm.api.activities import router as activities_router


# ── Lifespan ───────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时自动建表 / 扩展，关闭时释放连接池。"""
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    await close_redis()


# ── App ────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ──────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理，避免返回裸 500 错误。"""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": type(exc).__name__,
        },
    )


# ── Routers ────────────────────────────────────────────────

app.include_router(leads_router)
app.include_router(customers_router)
app.include_router(opportunities_router)
app.include_router(activities_router)


# ── Health ─────────────────────────────────────────────────


@app.get("/health", tags=["Health"])
async def health():
    """节点健康检查。

    返回值与 contracts/health-api.yaml 定义的 HealthResponse 一致:
        - status: ok / degraded / error
        - db: connected / disconnected
        - timestamp: ISO-8601
        - version: 应用版本
    """
    db_ok = await check_db_connection()

    if db_ok:
        status = "ok"
    else:
        status = "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db": "connected" if db_ok else "disconnected",
        "version": __version__,
    }
