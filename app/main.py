from fastapi import FastAPI

from app.api.router import api_router
from app.config import get_base_url, get_settings


settings = get_settings()


app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="Data platform API for Databricks integration running with Docker.",
    servers=[
        {"url": get_base_url(), "description": "Project host"},
        {"url": f"http://localhost:{settings.project_port}", "description": "Localhost"},
    ],
)

app.include_router(api_router)
