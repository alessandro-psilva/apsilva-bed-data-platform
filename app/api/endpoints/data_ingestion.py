from io import BytesIO

from databricks.sdk import WorkspaceClient
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.config import get_settings
from app.services.databricks import DatabricksConfigError, _validate_settings
from app.services.upload_history import list_upload_events, record_upload_event


router = APIRouter(prefix="/data-ingestion")


def _validate_file_name(file_name: str) -> str:
    if not file_name or "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid file name")

    if file_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid file name")

    if not file_name.strip():
        raise HTTPException(status_code=400, detail="Invalid file name")

    return file_name.strip()


def _validate_volume_segment(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned:
        raise HTTPException(status_code=400, detail=f"Invalid {label}")
    return cleaned


def _enforce_ingestion_target(schema_name: str, volume_name: str) -> None:
    settings = get_settings()
    allowed_schema = settings.data_ingestion_allowed_schema.strip().lower()
    allowed_volume = settings.data_ingestion_allowed_volume.strip().lower()

    if schema_name.strip().lower() != allowed_schema or volume_name.strip().lower() != allowed_volume:
        raise HTTPException(
            status_code=403,
            detail=(
                "Upload target not allowed by current ingestion policy: "
                f"schema={allowed_schema}, volume={allowed_volume}"
            ),
        )


def _sdk_status_code(exc: Exception) -> int:
    for attr_name in ("status_code", "http_status_code", "code"):
        value = getattr(exc, attr_name, None)
        if isinstance(value, int) and 400 <= value <= 599:
            return value
    return 502


def _sdk_error_detail(exc: Exception, fallback: str) -> str:
    detail = str(exc).strip()
    return detail or fallback


def _databricks_client() -> WorkspaceClient:
    _workspace_name, workspace_url, token = _validate_settings()
    return WorkspaceClient(host=workspace_url, token=token)


async def _list_databricks_volumes() -> list[dict[str, str]]:
    client = _databricks_client()
    items: list[dict[str, str]] = []

    try:
        catalogs = list(client.catalogs.list(max_results=100))
    except Exception as exc:
        raise HTTPException(
            status_code=_sdk_status_code(exc),
            detail=_sdk_error_detail(exc, "Failed to list Databricks catalogs"),
        ) from exc

    for catalog in catalogs:
        catalog_name = str(getattr(catalog, "name", "") or "").strip()
        if not catalog_name:
            continue

        try:
            schemas = list(client.schemas.list(catalog_name=catalog_name, max_results=100))
        except Exception as exc:
            if _sdk_status_code(exc) in {401, 403, 404}:
                continue
            raise HTTPException(
                status_code=_sdk_status_code(exc),
                detail=_sdk_error_detail(exc, "Failed to list Databricks schemas"),
            ) from exc

        for schema in schemas:
            schema_name = str(getattr(schema, "name", "") or "").strip()
            if not schema_name:
                continue

            try:
                volumes = list(
                    client.volumes.list(
                        catalog_name=catalog_name,
                        schema_name=schema_name,
                        max_results=100,
                    )
                )
            except Exception as exc:
                if _sdk_status_code(exc) in {401, 403, 404}:
                    continue
                raise HTTPException(
                    status_code=_sdk_status_code(exc),
                    detail=_sdk_error_detail(exc, "Failed to list Databricks volumes"),
                ) from exc

            for volume in volumes:
                volume_name = str(getattr(volume, "name", "") or "").strip()
                if not volume_name:
                    continue

                items.append(
                    {
                        "catalog_name": catalog_name,
                        "schema_name": schema_name,
                        "volume_name": volume_name,
                        "full_name": f"{catalog_name}.{schema_name}.{volume_name}",
                        "volume_path": f"/Volumes/{catalog_name}/{schema_name}/{volume_name}",
                    }
                )

    items.sort(key=lambda item: item["full_name"])
    return items


async def _upload_to_databricks_volume(
    *,
    catalog_name: str,
    schema_name: str,
    volume_name: str,
    file_name: str,
    content: bytes,
) -> str:
    client = _databricks_client()
    target_path = f"/Volumes/{catalog_name}/{schema_name}/{volume_name}/{file_name}"

    try:
        with BytesIO(content) as stream:
            client.files.upload(file_path=target_path, contents=stream, overwrite=True)
    except Exception as exc:
        raise HTTPException(
            status_code=_sdk_status_code(exc),
            detail=_sdk_error_detail(exc, "Upload to Databricks volume failed"),
        ) from exc

    return target_path


async def _verify_databricks_volume_file(target_path: str) -> dict[str, object]:
    client = _databricks_client()

    try:
        client.files.get_metadata(file_path=target_path)
        return {
            "method": "SDK_METADATA",
            "status_code": 200,
        }
    except Exception:
        try:
            # Fallback: force content stream creation to verify file readability.
            response = client.files.download(file_path=target_path)
            stream = getattr(response, "contents", None)
            if hasattr(stream, "read"):
                stream.read(1)
            return {
                "method": "SDK_DOWNLOAD",
                "status_code": 200,
            }
        except Exception as exc:
            raise HTTPException(
                status_code=_sdk_status_code(exc),
                detail=_sdk_error_detail(exc, "Upload verification failed"),
            ) from exc


@router.get("/volumes")
async def list_volumes() -> dict[str, object]:
    try:
        items = await _list_databricks_volumes()
    except DatabricksConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    raw_items = []
    settings = get_settings()
    allowed_schema = settings.data_ingestion_allowed_schema.strip().lower()
    allowed_volume = settings.data_ingestion_allowed_volume.strip().lower()

    for item in items:
        volume_name = str(item.get("volume_name", "")).strip().lower()
        schema_name = str(item.get("schema_name", "")).strip().lower()
        if schema_name == allowed_schema and volume_name == allowed_volume:
            raw_items.append(item)

    return {
        "items": raw_items,
        "count": len(raw_items),
    }


@router.get("/upload-history")
def upload_history(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, object]:
    items = list_upload_events(limit=limit)
    return {
        "items": items,
        "count": len(items),
    }


@router.post("/volumes/{catalog_name}/{schema_name}/{volume_name}/files")
async def upload_raw_file(
    catalog_name: str,
    schema_name: str,
    volume_name: str,
    file: UploadFile = File(...),
) -> dict[str, object]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    safe_catalog = _validate_volume_segment(catalog_name, "catalog name")
    safe_schema = _validate_volume_segment(schema_name, "schema name")
    safe_volume = _validate_volume_segment(volume_name, "volume name")
    _enforce_ingestion_target(safe_schema, safe_volume)
    file_name = _validate_file_name(file.filename)
    content = await file.read()
    content_size = len(content)

    max_upload_mb = get_settings().data_ingestion_max_upload_mb
    max_upload_bytes = max(1, int(max_upload_mb)) * 1024 * 1024
    if content_size > max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max upload size of {max_upload_mb} MB",
        )

    try:
        uploaded_path = await _upload_to_databricks_volume(
            catalog_name=safe_catalog,
            schema_name=safe_schema,
            volume_name=safe_volume,
            file_name=file_name,
            content=content,
        )
        verification = await _verify_databricks_volume_file(uploaded_path)
        try:
            record_upload_event(
                catalog_name=safe_catalog,
                schema_name=safe_schema,
                volume_name=safe_volume,
                file_name=file_name,
                size_bytes=content_size,
                status="success",
                verification_method=str(verification.get("method") or ""),
                databricks_volume_path=uploaded_path,
                error_detail=None,
            )
        except Exception:
            pass
    except DatabricksConfigError as exc:
        try:
            record_upload_event(
                catalog_name=safe_catalog,
                schema_name=safe_schema,
                volume_name=safe_volume,
                file_name=file_name,
                size_bytes=content_size,
                status="error",
                verification_method=None,
                databricks_volume_path=None,
                error_detail=str(exc),
            )
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException as exc:
        try:
            detail = str(exc.detail) if hasattr(exc, "detail") else str(exc)
            record_upload_event(
                catalog_name=safe_catalog,
                schema_name=safe_schema,
                volume_name=safe_volume,
                file_name=file_name,
                size_bytes=content_size,
                status="error",
                verification_method=None,
                databricks_volume_path=None,
                error_detail=detail,
            )
        except Exception:
            pass
        raise

    return {
        "volume": f"{safe_catalog}.{safe_schema}.{safe_volume}",
        "file_name": file_name,
        "size_bytes": content_size,
        "databricks_volume_path": uploaded_path,
        "upload_verified": True,
        "verification_method": verification.get("method"),
    }
