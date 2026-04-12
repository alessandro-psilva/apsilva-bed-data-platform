from fastapi.testclient import TestClient

from app.config import get_base_url
from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info() -> None:
    response = client.get("/info")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "apsilva-bed-fastapi-lab"
    assert payload["base_url"] == get_base_url()


def test_echo() -> None:
    response = client.post("/echo", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json() == {"echoed": "hello"}
