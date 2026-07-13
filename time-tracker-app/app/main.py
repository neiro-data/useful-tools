"""FastAPI application entrypoint for the Time Tracker app."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router as api_router
from app.config import get_settings
from app.db import get_connection
from app.errors import DomainError
from app.schema import init_db

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Bootstrap the SQLite schema (idempotent) before serving requests."""
    with get_connection() as conn:
        init_db(conn)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    """Translate a raised :class:`DomainError` into the standard error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "details": exc.details},
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Normalize FastAPI/pydantic's default 422 body into the standard error envelope."""
    fields = [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": {"fields": fields},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all fallback: translate any otherwise-unhandled exception into the standard error
    envelope, per ``app/API_CONTRACT.md``'s ``500 internal_error`` row.

    Registered after the more specific ``DomainError``/``RequestValidationError`` handlers above;
    FastAPI dispatches to the most specific matching handler for an exception's type, so those
    still take precedence and this only fires for exception types neither one covers. The real
    exception is logged server-side; the client only ever sees a generic message, never internal
    details or a stack trace.
    """
    logger.exception("Unhandled exception while processing request", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "details": None,
            },
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Simple liveness check."""
    return {"status": "ok"}
