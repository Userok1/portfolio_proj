from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes_auth import router as auth_router
from .api.routes_users import router as users_router
from .db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="auth-service", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health")
async def health():
    return {"ok": True}
