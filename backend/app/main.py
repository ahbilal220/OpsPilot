import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.routes import router as agents_router
from app.api.system import router as system_router
from app.auth.routes import router as auth_router
from app.core.config import Settings
from app.core.errors import ErrorEnvelope, error_response, install_error_handlers
from app.evidence.routes import router as evidence_router
from app.incidents.routes import router as incidents_router
from app.investigations.queue import enqueue_investigation
from app.telemetry.logging import configure_logging, request_id
from app.tools.bootstrap import build_tool_gateway
from app.tools.routes import router as tools_router


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        engine = create_async_engine(config.database_url.get_secret_value(), pool_pre_ping=True)
        cache = Redis.from_url(
            config.redis_url.get_secret_value(),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.redis = cache
        app.state.tool_gateway = build_tool_gateway(config, engine, app.state.session_factory)
        try:
            yield
        finally:
            await cache.aclose()
            await engine.dispose()

    app = FastAPI(
        title="OpsPilot",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        openapi_url="/api/v1/openapi.json",
        redoc_url=None,
    )
    app.state.settings = config
    app.state.enqueue_investigation = enqueue_investigation
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if re.fullmatch(r"[A-Za-z0-9_-]{1,64}", incoming) else str(uuid4())
        context = request_id.set(rid)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logging.getLogger("opspilot.api").error("request.failed")
                response = error_response(500, "INTERNAL_ERROR", "Internal server error")
            response.headers["X-Request-ID"] = rid
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            route = request.scope.get("route")
            logging.getLogger("opspilot.api").info(
                "request.completed",
                extra={
                    "method": request.method,
                    "route": getattr(route, "path", "unmatched"),
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            request_id.reset(context)

    for router in (
        system_router,
        auth_router,
        incidents_router,
        evidence_router,
        tools_router,
        agents_router,
    ):
        app.include_router(
            router,
            prefix="/api/v1",
            responses={
                code: {"model": ErrorEnvelope} for code in (401, 403, 409, 422, 429, 500, 503)
            },
        )
    return app


app = create_app()
