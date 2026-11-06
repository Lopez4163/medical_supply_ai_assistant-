from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as api_v1_router
from app.core.settings import get_settings
from app.db.session import dispose_database_engine


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
app.include_router(api_v1_router, prefix="/api/v1")
