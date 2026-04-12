from fastapi import APIRouter

from app.schemas.echo import EchoRequest, EchoResponse


router = APIRouter()


@router.post("", response_model=EchoResponse)
def echo(payload: EchoRequest) -> EchoResponse:
    return EchoResponse(echoed=payload.message)
