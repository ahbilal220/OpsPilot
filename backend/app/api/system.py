import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.core.errors import error_response

router = APIRouter(tags=["system"])


class Health(BaseModel):
    status: str


@router.get("/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok")


@router.get("/ready", response_model=Health)
async def ready(request: Request) -> Health | JSONResponse:
    try:
        async with asyncio.timeout(3):
            async with request.app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM users LIMIT 1"))
                revision = await conn.scalar(text("SELECT version_num FROM alembic_version"))
                if revision != "0005_orchestrated_investigation":
                    raise RuntimeError("Schema not ready")
            if not await request.app.state.redis.ping():
                raise RuntimeError("Redis not ready")
    except Exception:
        return error_response(503, "NOT_READY", "Required services or schema unavailable")
    return Health(status="ready")
