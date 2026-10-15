import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes_cart import router as cart_router
from .api.routes_catalog import router as catalog_router
from .api.routes_orders import router as orders_router
from .consumers import run_consumer
from .db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(run_consumer())
    yield
    task.cancel()


app = FastAPI(title="shop-service", lifespan=lifespan)
app.include_router(catalog_router)
app.include_router(cart_router)
app.include_router(orders_router)


@app.get("/health")
async def health():
    return {"ok": True}
