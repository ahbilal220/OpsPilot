import asyncio
import time

from fastapi import APIRouter, Query, Request
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


@router.get("/query", include_in_schema=False)
async def demo_prometheus_query(
    query: str = Query(min_length=1, max_length=500),
) -> dict[str, object]:
    """Serve the deterministic metric used by the public single-container demo."""
    values = {
        "demo_checkout_p95_latency_seconds": "1.91",
        "demo_checkout_db_queries_per_request": "43",
    }
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"__name__": query},
                    "value": [int(time.time()), values.get(query, "0")],
                }
            ],
        },
    }


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
