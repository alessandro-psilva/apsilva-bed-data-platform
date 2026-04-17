from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.databricks import (
    DatabricksConfigError,
    DatabricksRequestError,
    list_jobs,
    run_job,
)


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
        return run_job(job_id=job_id, parameters=parameters)
    except DatabricksConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DatabricksRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
