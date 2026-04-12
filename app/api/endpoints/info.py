from fastapi import APIRouter

from app.config import get_base_url


router = APIRouter()


@router.get("/info")
def app_info() -> dict[str, str]:
    return {
        "service": "apsilva-bed-fastapi-lab",
        "version": "0.1.0",
        "environment": "docker",
        "base_url": get_base_url(),
    }
