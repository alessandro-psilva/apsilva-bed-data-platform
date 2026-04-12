from fastapi import FastAPI

from app.api.router import api_router
from app.config import PROJECT_PORT, get_base_url


app = FastAPI(
    title="apsilva-bed-fastapi-lab",
    version="0.1.0",
    description="Backend-only FastAPI lab running with Docker.",
    servers=[
        {"url": get_base_url(), "description": "Project host"},
        {"url": f"http://localhost:{PROJECT_PORT}", "description": "Localhost"},
    ],
)

app.include_router(api_router)
