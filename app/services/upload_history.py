from typing import Any

import json

import psycopg

from app.config import get_settings


def _database_url() -> str:
    return get_settings().database_url.strip()


def _ensure_schema(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS upload_history (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            catalog_name TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            volume_name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            size_bytes BIGINT NOT NULL,
            status TEXT NOT NULL,
            verification_method TEXT,
            databricks_volume_path TEXT,
            error_detail TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS job_run_history (
            id BIGSERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            job_id BIGINT NOT NULL,
            run_id BIGINT,
            run_url TEXT,
            status TEXT NOT NULL,
            parameters_json TEXT,
            error_detail TEXT
        )
        """
    )


def record_upload_event(
    *,
    catalog_name: str,
    schema_name: str,
    volume_name: str,
    file_name: str,
    size_bytes: int,
    status: str,
    verification_method: str | None = None,
    databricks_volume_path: str | None = None,
    error_detail: str | None = None,
) -> None:
    db_url = _database_url()
    if not db_url:
        return

    with psycopg.connect(db_url) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO upload_history (
                catalog_name,
                schema_name,
                volume_name,
                file_name,
                size_bytes,
                status,
                verification_method,
                databricks_volume_path,
                error_detail
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                catalog_name,
                schema_name,
                volume_name,
                file_name,
                size_bytes,
                status,
                verification_method,
                databricks_volume_path,
                error_detail,
            ),
        )
        conn.commit()


def list_upload_events(*, limit: int = 50) -> list[dict[str, Any]]:
    db_url = _database_url()
    if not db_url:
        return []

    with psycopg.connect(db_url) as conn:
        _ensure_schema(conn)
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                    created_at,
                    catalog_name,
                    schema_name,
                    volume_name,
                    file_name,
                    size_bytes,
                    status,
                    verification_method,
                    databricks_volume_path,
                    error_detail
                FROM upload_history
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [dict(row) for row in rows]


def record_job_run_event(
    *,
    job_id: int,
    run_id: int | None,
    run_url: str | None,
    status: str,
    parameters: dict[str, str] | None = None,
    error_detail: str | None = None,
) -> None:
    db_url = _database_url()
    if not db_url:
        return

    parameters_json = json.dumps(parameters) if parameters is not None else None

    with psycopg.connect(db_url) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO job_run_history (
                job_id,
                run_id,
                run_url,
                status,
                parameters_json,
                error_detail
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                job_id,
                run_id,
                run_url,
                status,
                parameters_json,
                error_detail,
            ),
        )
        conn.commit()


def list_job_run_events(*, limit: int = 50) -> list[dict[str, Any]]:
    db_url = _database_url()
    if not db_url:
        return []

    with psycopg.connect(db_url) as conn:
        _ensure_schema(conn)
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(
                """
                SELECT
                    created_at,
                    job_id,
                    run_id,
                    run_url,
                    status,
                    parameters_json,
                    error_detail
                FROM job_run_history
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    items = [dict(row) for row in rows]
    for item in items:
        raw_parameters = item.get("parameters_json")
        if isinstance(raw_parameters, str) and raw_parameters:
            try:
                item["parameters"] = json.loads(raw_parameters)
            except json.JSONDecodeError:
                item["parameters"] = raw_parameters
        else:
            item["parameters"] = None
        item.pop("parameters_json", None)
    return items
