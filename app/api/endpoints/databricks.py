from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.databricks import (
    DatabricksConfigError,
    DatabricksRequestError,
    list_jobs,
)


router = APIRouter(prefix="/databricks")


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
