import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes_payments import router as pay_router
from .api.routes_webhooks import router as wh_router
from .consumers import run_consumer
from .db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(run_consumer())
    yield
    task.cancel()


app = FastAPI(title="payment-service", lifespan=lifespan)
app.include_router(pay_router)
app.include_router(wh_router)


@app.get("/health")
async def health():
    return {"ok": True}
