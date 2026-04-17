from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_databricks_jobs_success(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeJob:
        def as_dict(self) -> dict:
            return {
                "job_id": 1,
                "settings": {"name": "daily-import"},
            }

    class FakeJobsAPI:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def list(self, **kwargs):
            self.calls.append(kwargs)
            if kwargs == {"limit": 25, "offset": 0}:
                return [FakeJob()]
            if kwargs == {"limit": 1, "offset": 1}:
                return []
            raise AssertionError(f"Unexpected list kwargs: {kwargs}")

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            assert host == "https://dbc-ffed086d-34da.cloud.databricks.com/"
            assert token == "test-token"
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.get("/databricks/jobs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["job_id"] == 1
    assert payload["pagination"] == {
        "limit": 25,
        "offset": 0,
        "returned": 1,
        "has_more": False,
        "next_offset": None,
    }


def test_databricks_jobs_query_params_and_has_more(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeJob:
        def __init__(self, job_id: int) -> None:
            self.job_id = job_id

        def as_dict(self) -> dict:
            return {
                "job_id": self.job_id,
                "settings": {"name": f"job-{self.job_id}"},
            }

    class FakeJobsAPI:
        def list(self, **kwargs):
            if kwargs == {"limit": 2, "offset": 10, "expand_tasks": True}:
                return [FakeJob(11), FakeJob(12)]
            if kwargs == {"limit": 1, "offset": 12}:
                return [FakeJob(13)]
            raise AssertionError(f"Unexpected list kwargs: {kwargs}")

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.get("/databricks/jobs?limit=2&offset=10&expand_tasks=true")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"job_id": 11, "settings": {"name": "job-11"}},
            {"job_id": 12, "settings": {"name": "job-12"}},
        ],
        "pagination": {
            "limit": 2,
            "offset": 10,
            "returned": 2,
            "has_more": True,
            "next_offset": 12,
        },
    }


def test_databricks_jobs_missing_configuration(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "")
    monkeypatch.setenv("DATABRICKS_TOKEN", "")
    get_settings.cache_clear()

    response = client.get("/databricks/jobs")
    assert response.status_code == 503


def test_databricks_jobs_request_error(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeJobsAPI:
        def list(self, **kwargs):
            raise RuntimeError("sdk failure")

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.get("/databricks/jobs")
    assert response.status_code == 502


def test_databricks_jobs_propagates_sdk_status_code(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeSDKError(RuntimeError):
        status_code = 401

    class FakeJobsAPI:
        def list(self, **kwargs):
            raise FakeSDKError("unauthorized")

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.get("/databricks/jobs")
    assert response.status_code == 401


def test_databricks_jobs_success_with_vault_secret(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_BACKEND", "vault")
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "")
    monkeypatch.setenv("DATABRICKS_TOKEN_SECRET_NAME", "databricks_token")
    get_settings.cache_clear()

    def fake_get_secret(secret_name: str) -> tuple[str, str]:
        assert secret_name == "databricks_token"
        return "vault-token-value", "vault"

    class FakeJobsAPI:
        def list(self, **kwargs):
            if kwargs == {"limit": 25, "offset": 0}:
                return []
            if kwargs == {"limit": 1, "offset": 0}:
                return []
            raise AssertionError(f"Unexpected list kwargs: {kwargs}")

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            assert token == "vault-token-value"
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.get_secret", fake_get_secret)
    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.get("/databricks/jobs")
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "pagination": {
            "limit": 25,
            "offset": 0,
            "returned": 0,
            "has_more": False,
            "next_offset": None,
        },
    }
