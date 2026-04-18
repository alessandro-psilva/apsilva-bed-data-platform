from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "apsilva-bed-data-platform"
    project_host: str = "apsilva-bed-data-platform.localhost"
    project_port: int = 8000
    app_env: str = "docker"
    log_level: str = "info"
    secret_backend: str = "env"
    vault_addr: str = "http://vault:8200"
    vault_token: str = "dev-root-token"
    vault_kv_mount: str = "secret"
    vault_secret_value_key: str = "value"
    database_url: str = ""
    databricks_workspace_name: str = ""
    databricks_workspace: str = ""
    databricks_token: str = ""
    databricks_token_secret_name: str = "databricks_token"
    cors_allowed_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://apsilva-fed-data-platform.localhost:8080"
    data_ingestion_allowed_schema: str = "ingestion"
    data_ingestion_allowed_volume: str = "raw"
    data_ingestion_max_upload_mb: int = 15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def base_url(self) -> str:
        return f"http://{self.project_host}:{self.project_port}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


PROJECT_HOST = get_settings().project_host
PROJECT_PORT = get_settings().project_port


def get_base_url() -> str:
    return get_settings().base_url
