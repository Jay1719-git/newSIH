from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_exception_handlers, make_request_id
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import get_engine, get_session_factory
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        get_session_factory.cache_clear()
        if get_engine.cache_info().currsize:
            get_engine().dispose()
        get_engine.cache_clear()

    application = FastAPI(
        title=app_settings.app_name,
        version="0.1.0",
        description=(
            "Synthetic local demo API. APAAR format validation is not official identity "
            "verification; no official APAAR, DigiLocker, or AICTE connectivity is provided."
        ),
        openapi_url=f"{app_settings.api_base_path}/openapi.json",
        docs_url="/docs" if app_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.settings = app_settings

    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    @application.middleware("http")
    async def request_context(request: Request, call_next: Callable) -> Response:
        request.state.request_id = make_request_id(request.headers.get("X-Request-ID"))
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%d",
            request.state.request_id,
            request.method,
            request.url.path,
            response.status_code,
            int((time.perf_counter() - started) * 1000),
        )
        return response

    @application.get("/health", response_model=HealthResponse, operation_id="getRootHealth")
    def get_root_health() -> HealthResponse:
        return HealthResponse()

    application.include_router(api_router, prefix=app_settings.api_base_path)
    install_exception_handlers(application)
    return application


app = create_app()
