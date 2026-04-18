from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.databricks import (
    DatabricksConfigError,
    DatabricksRequestError,
    list_jobs,
    run_job,
)
from app.services.upload_history import list_job_run_events, record_job_run_event


router = APIRouter(prefix="/databricks")


class RunJobRequest(BaseModel):
    parameters: dict[str, str] | None = None


@router.get("/jobs")
def read_databricks_jobs(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    expand_tasks: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        return list_jobs(limit=limit, offset=offset, expand_tasks=expand_tasks)
    except DatabricksConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DatabricksRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/run")
def trigger_databricks_job(job_id: int, payload: RunJobRequest | None = None) -> dict[str, Any]:
    parameters = payload.parameters if payload else None
    try:
        response = run_job(job_id=job_id, parameters=parameters)
        run_id: int | None = None
        raw_run_id = response.get("run_id")
        if isinstance(raw_run_id, int):
            run_id = raw_run_id
        elif isinstance(raw_run_id, str) and raw_run_id.isdigit():
            run_id = int(raw_run_id)

        try:
            record_job_run_event(
                job_id=job_id,
                run_id=run_id,
                run_url=str(response.get("run_url") or "") or None,
                status="success",
                parameters=parameters,
                error_detail=None,
            )
        except Exception:
            pass
        return response
    except DatabricksConfigError as exc:
        try:
            record_job_run_event(
                job_id=job_id,
                run_id=None,
                run_url=None,
                status="error",
                parameters=parameters,
                error_detail=str(exc),
            )
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DatabricksRequestError as exc:
        try:
            record_job_run_event(
                job_id=job_id,
                run_id=None,
                run_url=None,
                status="error",
                parameters=parameters,
                error_detail=str(exc),
            )
        except Exception:
            pass
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/run-history")
def run_history(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    items = list_job_run_events(limit=limit)
    return {
        "items": items,
        "count": len(items),
    }
