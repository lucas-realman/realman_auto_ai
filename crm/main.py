from contextlib import asynccontextmanager
from fastapi import FastAPI
from crm.config import settings
from crm.database import engine
from crm.services.event_publisher import close_redis
from crm.api.leads import router as leads_router
from crm.api.customers import router as customers_router
from crm.api.opportunities import router as opportunities_router
from crm.api.activities import router as activities_router


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()
    await close_redis()


app = FastAPI(title="Sirus AI-CRM", version="0.1.0", lifespan=lifespan)

app.include_router(leads_router)
app.include_router(customers_router)
app.include_router(opportunities_router)
app.include_router(activities_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "crm"}
