from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from crm.config import settings
from crm.database import engine
from crm.models import Base  # ensure all models are registered
from crm.services.event_publisher import close_redis
from crm.api.leads import router as leads_router
from crm.api.customers import router as customers_router
from crm.api.opportunities import router as opportunities_router
from crm.api.activities import router as activities_router


@asynccontextmanager
async def lifespan(app):
    # Dev mode: auto-create tables
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    await close_redis()


app = FastAPI(title="Sirus AI-CRM", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads_router)
app.include_router(customers_router)
app.include_router(opportunities_router)
app.include_router(activities_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "crm"}
