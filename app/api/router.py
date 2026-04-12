from fastapi import APIRouter

from app.api.endpoints.echo import router as echo_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.info import router as info_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(info_router, tags=["system"])
api_router.include_router(echo_router, prefix="/echo", tags=["echo"])
