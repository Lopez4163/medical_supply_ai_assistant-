from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.products import router as products_router
from app.api.v1.quotations import router as quotations_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.support import router as support_router
from app.db.session import get_database_engine, is_database_ready

router = APIRouter()
router.include_router(chat_router)
router.include_router(conversations_router)
router.include_router(products_router)
router.include_router(quotations_router)
router.include_router(sessions_router)
router.include_router(support_router)


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
