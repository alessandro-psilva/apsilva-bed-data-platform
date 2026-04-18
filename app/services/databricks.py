from typing import Any

from databricks.sdk import WorkspaceClient

from app.config import get_settings
from app.services.secrets import get_secret


class DatabricksConfigError(ValueError):
    pass


class DatabricksRequestError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _extract_status_code(exc: Exception) -> int:
    for attr_name in ("status_code", "http_status_code", "code"):
        value = getattr(exc, attr_name, None)
        if isinstance(value, int) and 400 <= value <= 599:
            return value
    return 502


def _resolve_databricks_token() -> str:
    settings = get_settings()
    secret_name = settings.databricks_token_secret_name.strip()

    if settings.secret_backend.lower() == "vault":
        if not secret_name:
            raise DatabricksConfigError(
                "Databricks token secret name is empty. Set DATABRICKS_TOKEN_SECRET_NAME."
            )
        try:
            token, _backend = get_secret(secret_name)
        except KeyError as exc:
            raise DatabricksConfigError(
                f"Databricks token not found in secret backend: {secret_name}"
            ) from exc
        if not token.strip():
            raise DatabricksConfigError(
                f"Databricks token secret '{secret_name}' is empty."
            )
        return token.strip()

    if settings.databricks_token.strip():
        return settings.databricks_token.strip()

    if secret_name:
        try:
            token, _backend = get_secret(secret_name)
            if token.strip():
                return token.strip()
        except KeyError:
            pass

    raise DatabricksConfigError(
        "Databricks token is missing. Set DATABRICKS_TOKEN or configure secret backend with DATABRICKS_TOKEN_SECRET_NAME."
    )


def _validate_settings() -> tuple[str, str, str]:
    settings = get_settings()
    workspace_name = settings.databricks_workspace_name.strip()
    workspace_url = settings.databricks_workspace.strip()
    token = _resolve_databricks_token()

    if not workspace_name or not workspace_url:
        raise DatabricksConfigError(
            "Databricks is not configured. Set DATABRICKS_WORKSPACE_NAME and DATABRICKS_WORKSPACE."
        )

    return workspace_name, workspace_url, token


def _model_to_dict(model: Any) -> dict[str, Any]:
    """Convert Databricks SDK model to dictionary."""
    import inspect
    
    # Try as_dict() method
    try:
        return model.as_dict()
    except (AttributeError, KeyError, TypeError):
        pass
    
    # Try as_shallow_dict() method
    try:
        return model.as_shallow_dict()
    except (AttributeError, KeyError, TypeError):
        pass
    
    # Try vars() - works for most Python objects, filtering out methods and privates
    try:
        result = {}
        for key, value in vars(model).items():
            # Skip private attributes and methods
            if not key.startswith('_') and not inspect.ismethod(value) and not inspect.isfunction(value):
                result[key] = value
        if result:
            return result
    except TypeError:
        pass
    
    # Try dict(model.__dict__) with filtering
    try:
        if hasattr(model, "__dict__"):
            result = {}
            for key, value in model.__dict__.items():
                # Skip private attributes and methods
                if not key.startswith('_') and not inspect.ismethod(value) and not inspect.isfunction(value):
                    result[key] = value
            if result:
                return result
    except (TypeError, ValueError, KeyError):
        pass
    
    # Last resort: return as string wrapped in dict
    return {"value": str(model)}


def _has_next_page(client: WorkspaceClient, current_offset: int, returned: int) -> bool:
    if returned <= 0:
        return False

    probe_offset = current_offset + returned
    probe_items = list(client.jobs.list(limit=1, offset=probe_offset))
    return len(probe_items) > 0


def list_jobs(*, limit: int | None = None, offset: int | None = None, expand_tasks: bool = False) -> dict[str, Any]:
    _workspace_name, workspace_url, token = _validate_settings()

    effective_limit = limit if limit is not None else 25
    effective_offset = offset if offset is not None else 0

    list_kwargs: dict[str, Any] = {}
    list_kwargs["limit"] = effective_limit
    list_kwargs["offset"] = effective_offset
    if expand_tasks:
        list_kwargs["expand_tasks"] = True

    try:
        client = WorkspaceClient(host=workspace_url, token=token)
        jobs = [_model_to_dict(job) for job in client.jobs.list(**list_kwargs)]
    except Exception as exc:
        status_code = _extract_status_code(exc)
        raise DatabricksRequestError(
            f"Databricks SDK error: {exc}",
            status_code=status_code,
        ) from exc

    if len(jobs) < effective_limit:
        has_more = False
    else:
        try:
            has_more = _has_next_page(client, effective_offset, len(jobs))
        except Exception as exc:
            status_code = _extract_status_code(exc)
            raise DatabricksRequestError(
                f"Databricks SDK error while probing pagination: {exc}",
                status_code=status_code,
            ) from exc

    next_offset = effective_offset + len(jobs) if has_more else None

    return {
        "items": jobs,
        "pagination": {
            "limit": effective_limit,
            "offset": effective_offset,
            "returned": len(jobs),
            "has_more": has_more,
            "next_offset": next_offset,
        },
    }


def run_job(*, job_id: int, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    _workspace_name, workspace_url, token = _validate_settings()

    run_kwargs: dict[str, Any] = {"job_id": job_id}
    if parameters:
        run_kwargs["job_parameters"] = parameters

    try:
        client = WorkspaceClient(host=workspace_url, token=token)
        run_response = client.jobs.run_now(**run_kwargs)
    except TypeError as exc:
        if not parameters:
            raise DatabricksRequestError(f"Databricks SDK error: {exc}") from exc
        try:
            # Compatibility fallback for SDK versions that do not support job_parameters.
            run_response = client.jobs.run_now(job_id=job_id, notebook_params=parameters)
        except Exception as inner_exc:
            status_code = _extract_status_code(inner_exc)
            raise DatabricksRequestError(
                f"Databricks SDK error: {inner_exc}",
                status_code=status_code,
            ) from inner_exc
    except Exception as exc:
        status_code = _extract_status_code(exc)
        raise DatabricksRequestError(
            f"Databricks SDK error: {exc}",
            status_code=status_code,
        ) from exc

    response = _model_to_dict(run_response)

    nested_raw = response.get("response")
    if isinstance(nested_raw, dict):
        nested_response = nested_raw
    else:
        nested_response = {
            "run_id": getattr(nested_raw, "run_id", None),
            "number_in_job": getattr(nested_raw, "number_in_job", None),
        }
    run_id = (
        response.get("run_id")
        or response.get("number_in_job")
        or nested_response.get("run_id")
        or nested_response.get("number_in_job")
    )
    if run_id is not None:
        workspace_base = workspace_url.rstrip("/")
        response["run_id"] = run_id
        response["run_url"] = f"{workspace_base}/jobs/{job_id}/runs/{run_id}"

    return response
