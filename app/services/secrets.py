import os

import httpx

from app.config import get_settings


def _to_env_secret_name(secret_name: str) -> str:
    normalized = "".join(ch if ch.isalnum() else "_" for ch in secret_name)
    return f"SECRET_{normalized.upper()}"


def get_secret(secret_name: str) -> tuple[str, str]:
    settings = get_settings()

    if settings.secret_backend.lower() == "vault":
        value = _get_secret_from_vault(secret_name)
        return value, "vault"

    env_name = _to_env_secret_name(secret_name)
    value = os.getenv(env_name)
    if value is None:
        raise KeyError(f"Secret not found in env: {env_name}")
    return value, "env"


def _get_secret_from_vault(secret_name: str) -> str:
    settings = get_settings()
    path = f"{settings.vault_addr}/v1/{settings.vault_kv_mount}/data/{secret_name}"
    headers = {"X-Vault-Token": settings.vault_token}

    with httpx.Client(timeout=5.0) as client:
        response = client.get(path, headers=headers)

    if response.status_code == 404:
        raise KeyError(f"Secret not found in vault: {secret_name}")
    response.raise_for_status()

    payload = response.json()
    try:
        return payload["data"]["data"][settings.vault_secret_value_key]
    except KeyError as exc:
        raise KeyError(
            f"Vault secret missing key '{settings.vault_secret_value_key}'"
        ) from exc