from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.errors import install_exception_handlers
from app.core.settings import get_settings
from app.db.session import dispose_database_engine


class TrustedOriginCORSMiddleware(CORSMiddleware):
    """Use the validated application allowlist for credentialed browser CORS."""

    def is_allowed_origin(self, origin: str) -> bool:
        return origin in get_settings().quotation_trusted_origins


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings()
    yield
    await dispose_database_engine()


app = FastAPI(
    title="BioMedicHospicare AI Supply Assistant API",
    description="Synthetic-data portfolio demonstration API.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    TrustedOriginCORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
)
install_exception_handlers(app)
app.include_router(api_v1_router, prefix="/api/v1")
