from fastapi import APIRouter

from app.api.endpoints.data_ingestion import router as data_ingestion_router
from app.api.endpoints.databricks import router as databricks_router
from app.api.endpoints.health import router as health_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(databricks_router, tags=["databricks"])
api_router.include_router(data_ingestion_router, tags=["data-ingestion"])
