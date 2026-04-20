from fastapi import HTTPException
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
            "next_page_id": 12,
        },
    }


def test_databricks_jobs_next_page_id_query_param(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeJob:
        def as_dict(self) -> dict:
            return {
                "job_id": 21,
                "settings": {"name": "job-21"},
            }

    class FakeJobsAPI:
        def list(self, **kwargs):
            if kwargs == {"limit": 1, "offset": 20, "expand_tasks": True}:
                return [FakeJob()]
            if kwargs == {"limit": 1, "offset": 21}:
                return []
            raise AssertionError(f"Unexpected list kwargs: {kwargs}")

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    # next_page_id must drive pagination position.
    response = client.get("/databricks/jobs?limit=1&offset=0&next_page_id=20&expand_tasks=true")
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"job_id": 21, "settings": {"name": "job-21"}},
        ],
        "pagination": {
            "limit": 1,
            "offset": 20,
            "returned": 1,
            "has_more": False,
            "next_offset": None,
            "next_page_id": None,
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


def test_databricks_run_job_without_parameters(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeRunResponse:
        def as_dict(self) -> dict:
            return {"run_id": 12345, "number_in_job": 7}

    class FakeJobsAPI:
        def run_now(self, **kwargs):
            assert kwargs == {"job_id": 123}
            return FakeRunResponse()

        def list(self, **kwargs):
            return []

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.post("/databricks/jobs/123/run")
    assert response.status_code == 200
    assert response.json() == {
        "run_id": 12345,
        "number_in_job": 7,
        "run_url": "https://dbc-ffed086d-34da.cloud.databricks.com/jobs/123/runs/12345",
    }


def test_databricks_run_job_with_parameters(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    class FakeRunResponse:
        def as_dict(self) -> dict:
            return {"run_id": 67890}

    class FakeJobsAPI:
        def run_now(self, **kwargs):
            assert kwargs == {
                "job_id": 456,
                "job_parameters": {"country": "br", "mode": "full"},
            }
            return FakeRunResponse()

        def list(self, **kwargs):
            return []

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)

    response = client.post(
        "/databricks/jobs/456/run",
        json={"parameters": {"country": "br", "mode": "full"}},
    )
    assert response.status_code == 200
    assert response.json() == {
        "run_id": 67890,
        "run_url": "https://dbc-ffed086d-34da.cloud.databricks.com/jobs/456/runs/67890",
    }


def test_databricks_run_job_records_success_history(monkeypatch) -> None:
    monkeypatch.setenv("DATABRICKS_WORKSPACE_NAME", "dbwawsdv")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "https://dbc-ffed086d-34da.cloud.databricks.com/")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test-token")
    get_settings.cache_clear()

    recorded_events: list[dict] = []

    class FakeRunResponse:
        def as_dict(self) -> dict:
            return {"run_id": 67890}

    class FakeJobsAPI:
        def run_now(self, **kwargs):
            assert kwargs == {
                "job_id": 456,
                "job_parameters": {"country": "br"},
            }
            return FakeRunResponse()

        def list(self, **kwargs):
            return []

    class FakeWorkspaceClient:
        def __init__(self, host: str, token: str) -> None:
            self.jobs = FakeJobsAPI()

    def fake_record_job_run_event(**kwargs) -> None:
        recorded_events.append(kwargs)

    monkeypatch.setattr("app.services.databricks.WorkspaceClient", FakeWorkspaceClient)
    monkeypatch.setattr("app.api.endpoints.databricks.record_job_run_event", fake_record_job_run_event)

    response = client.post(
        "/databricks/jobs/456/run",
        json={"parameters": {"country": "br"}},
    )

    assert response.status_code == 200
    assert len(recorded_events) == 1
    assert recorded_events[0]["job_id"] == 456
    assert recorded_events[0]["run_id"] == 67890
    assert recorded_events[0]["status"] == "success"


def test_databricks_run_history(monkeypatch) -> None:
    def fake_list_job_run_events(*, limit: int = 50) -> list[dict]:
        assert limit == 20
        return [
            {
                "created_at": "2026-04-18T12:00:00+00:00",
                "job_id": 123,
                "run_id": 987,
                "run_url": "https://workspace/jobs/123/runs/987",
                "status": "success",
                "parameters": {"country": "br"},
                "error_detail": None,
            }
        ]

    monkeypatch.setattr("app.api.endpoints.databricks.list_job_run_events", fake_list_job_run_events)

    response = client.get("/databricks/run-history?limit=20")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "created_at": "2026-04-18T12:00:00+00:00",
                "job_id": 123,
                "run_id": 987,
                "run_url": "https://workspace/jobs/123/runs/987",
                "status": "success",
                "parameters": {"country": "br"},
                "error_detail": None,
            }
        ],
        "count": 1,
    }


def test_data_ingestion_list_volumes(monkeypatch) -> None:
    get_settings.cache_clear()

    async def fake_list() -> list[dict[str, str]]:
        return [
            {
                "catalog_name": "main",
                "schema_name": "ingestion",
                "volume_name": "raw",
                "full_name": "main.ingestion.raw",
                "volume_path": "/Volumes/main/ingestion/raw",
            },
            {
                "catalog_name": "samples",
                "schema_name": "raw",
                "volume_name": "landing",
                "full_name": "samples.raw.landing",
                "volume_path": "/Volumes/samples/raw/landing",
            }
        ]

    monkeypatch.setattr("app.api.endpoints.data_ingestion._list_databricks_volumes", fake_list)

    response = client.get("/data-ingestion/volumes")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "catalog_name": "main",
                "schema_name": "ingestion",
                "volume_name": "raw",
                "full_name": "main.ingestion.raw",
                "volume_path": "/Volumes/main/ingestion/raw",
            }
        ],
        "count": 1,
    }


def test_data_ingestion_list_volumes_respects_env_rules(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "raw")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "landing")
    get_settings.cache_clear()

    async def fake_list() -> list[dict[str, str]]:
        return [
            {
                "catalog_name": "main",
                "schema_name": "ingestion",
                "volume_name": "raw",
                "full_name": "main.ingestion.raw",
                "volume_path": "/Volumes/main/ingestion/raw",
            },
            {
                "catalog_name": "samples",
                "schema_name": "raw",
                "volume_name": "landing",
                "full_name": "samples.raw.landing",
                "volume_path": "/Volumes/samples/raw/landing",
            },
        ]

    monkeypatch.setattr("app.api.endpoints.data_ingestion._list_databricks_volumes", fake_list)

    response = client.get("/data-ingestion/volumes")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "catalog_name": "samples",
                "schema_name": "raw",
                "volume_name": "landing",
                "full_name": "samples.raw.landing",
                "volume_path": "/Volumes/samples/raw/landing",
            }
        ],
        "count": 1,
    }


def test_data_ingestion_upload_to_selected_volume(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "raw")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "landing")
    get_settings.cache_clear()
    recorded_events: list[dict] = []

    async def fake_upload(
        *,
        catalog_name: str,
        schema_name: str,
        volume_name: str,
        file_name: str,
        content: bytes,
    ) -> str:
        assert catalog_name == "main"
        assert schema_name == "raw"
        assert volume_name == "landing"
        assert file_name == "clientes.csv"
        assert content == b"id,nome\n1,Ana\n"
        return "/Volumes/main/raw/landing/clientes.csv"

    async def fake_verify(target_path: str) -> dict[str, object]:
        assert target_path == "/Volumes/main/raw/landing/clientes.csv"
        return {"method": "HEAD", "status_code": 200}

    def fake_record_upload_event(**kwargs) -> None:
        recorded_events.append(kwargs)

    monkeypatch.setattr("app.api.endpoints.data_ingestion._upload_to_databricks_volume", fake_upload)
    monkeypatch.setattr("app.api.endpoints.data_ingestion._verify_databricks_volume_file", fake_verify)
    monkeypatch.setattr("app.api.endpoints.data_ingestion.record_upload_event", fake_record_upload_event)

    response = client.post(
        "/data-ingestion/volumes/main/raw/landing/files",
        files={"file": ("clientes.csv", "id,nome\n1,Ana\n", "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "volume": "main.raw.landing",
        "file_name": "clientes.csv",
        "size_bytes": 14,
        "databricks_volume_path": "/Volumes/main/raw/landing/clientes.csv",
        "upload_verified": True,
        "verification_method": "HEAD",
    }
    assert len(recorded_events) == 1
    assert recorded_events[0]["status"] == "success"


def test_data_ingestion_upload_verification_failure(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "raw")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "landing")
    get_settings.cache_clear()
    recorded_events: list[dict] = []

    async def fake_upload(
        *,
        catalog_name: str,
        schema_name: str,
        volume_name: str,
        file_name: str,
        content: bytes,
    ) -> str:
        return "/Volumes/main/raw/landing/clientes.csv"

    async def fake_verify(_target_path: str) -> dict[str, object]:
        raise HTTPException(status_code=502, detail="Upload verification failed")

    def fake_record_upload_event(**kwargs) -> None:
        recorded_events.append(kwargs)

    monkeypatch.setattr("app.api.endpoints.data_ingestion._upload_to_databricks_volume", fake_upload)
    monkeypatch.setattr("app.api.endpoints.data_ingestion._verify_databricks_volume_file", fake_verify)
    monkeypatch.setattr("app.api.endpoints.data_ingestion.record_upload_event", fake_record_upload_event)

    response = client.post(
        "/data-ingestion/volumes/main/raw/landing/files",
        files={"file": ("clientes.csv", "id,nome\n1,Ana\n", "text/csv")},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Upload verification failed"
    assert len(recorded_events) == 1
    assert recorded_events[0]["status"] == "error"


def test_data_ingestion_upload_history(monkeypatch) -> None:
    get_settings.cache_clear()

    def fake_list_upload_events(*, limit: int = 50) -> list[dict]:
        assert limit == 20
        return [
            {
                "created_at": "2026-04-18T10:00:00+00:00",
                "catalog_name": "main",
                "schema_name": "raw",
                "volume_name": "landing",
                "file_name": "clientes.csv",
                "size_bytes": 1024,
                "status": "success",
                "verification_method": "HEAD",
                "databricks_volume_path": "/Volumes/main/raw/landing/clientes.csv",
                "error_detail": None,
            }
        ]

    monkeypatch.setattr("app.api.endpoints.data_ingestion.list_upload_events", fake_list_upload_events)

    response = client.get("/data-ingestion/upload-history?limit=20")
    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["status"] == "success"


def test_data_ingestion_rejects_invalid_filename(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "raw")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "landing")
    get_settings.cache_clear()

    response = client.post(
        "/data-ingestion/volumes/main/raw/landing/files",
        files={"file": ("../segredo.txt", "x", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid file name"


def test_data_ingestion_returns_503_when_databricks_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "raw")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "landing")
    monkeypatch.setenv("DATABRICKS_WORKSPACE", "")
    get_settings.cache_clear()

    response = client.post(
        "/data-ingestion/volumes/main/raw/landing/files",
        files={"file": ("clientes.csv", "id,nome\n1,Ana\n", "text/csv")},
    )
    assert response.status_code == 503


def test_data_ingestion_rejects_file_above_max_size(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "raw")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "landing")
    monkeypatch.setenv("DATA_INGESTION_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    payload = "x" * (1024 * 1024 + 1)
    response = client.post(
        "/data-ingestion/volumes/main/raw/landing/files",
        files={"file": ("grande.csv", payload, "text/csv")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "File exceeds max upload size of 1 MB"


def test_data_ingestion_rejects_upload_outside_env_policy(monkeypatch) -> None:
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_SCHEMA", "ingestion")
    monkeypatch.setenv("DATA_INGESTION_ALLOWED_VOLUME", "raw")
    get_settings.cache_clear()

    response = client.post(
        "/data-ingestion/volumes/main/raw/landing/files",
        files={"file": ("clientes.csv", "id,nome\n1,Ana\n", "text/csv")},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Upload target not allowed by current ingestion policy: schema=ingestion, volume=raw"
    )
