from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.session import get_database_engine, is_database_ready

router = APIRouter()


class LivenessResponse(BaseModel):
    status: str


@router.get("/live", response_model=LivenessResponse, tags=["system"])
async def get_liveness() -> LivenessResponse:
    """Confirm that the application process is accepting requests."""
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=LivenessResponse, tags=["system"])
async def get_readiness(
    engine: AsyncEngine = Depends(get_database_engine),
) -> LivenessResponse | JSONResponse:
    """Confirm that PostgreSQL and its required pgvector extension are available."""
    if await is_database_ready(engine):
        return LivenessResponse(status="ok")
    return JSONResponse(status_code=503, content={"status": "unavailable"})
