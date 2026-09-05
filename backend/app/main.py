from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.admin import router as admin_router
from app.api.routes import router
from app.api.v2.product_routes import router as product_router
from app.api.v2.routes import router as v2_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Explainable health, growth, and activity intelligence for open-source repositories."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(v2_router, prefix="/api/v2")
app.include_router(product_router, prefix="/api/v2")


@app.middleware("http")
async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; base-uri 'self'"
    if request.url.path.startswith("/api/v1/admin"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health", tags=["operations"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
