# apsilva-bed-data-platform

API FastAPI para consultar jobs do Databricks com execução docker-first.

## Requisitos

- Docker
- Docker Compose

## Configuração

Crie seu arquivo de ambiente:

```bash
cp .env.example .env
```

Variáveis principais:

- `PROJECT_HOST` (padrão: `apsilva-bed-data-platform.localhost`)
- `PROJECT_PORT` (padrão: `8000`)
- `APP_ENV` (padrão: `docker`)
- `LOG_LEVEL` (padrão: `info`)
- `SECRET_BACKEND` (`env` ou `vault`)
- `VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_KV_MOUNT`, `VAULT_SECRET_VALUE_KEY`
- `DATABASE_URL` (PostgreSQL para historico de uploads)
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `DATA_INGESTION_ALLOWED_SCHEMA` (padrão: `ingestion`)
- `DATA_INGESTION_ALLOWED_VOLUME` (padrão: `raw`)
- `DATA_INGESTION_MAX_UPLOAD_MB` (padrão: `15`)
- `DATABRICKS_WORKSPACE_NAME`
- `DATABRICKS_WORKSPACE`
- `DATABRICKS_TOKEN`
- `DATABRICKS_TOKEN_SECRET_NAME` (padrão: `databricks_token`)

## Executar

```bash
docker compose up --build
```

## Acessos

- API: http://apsilva-bed-data-platform.localhost:8000
- Swagger: http://apsilva-bed-data-platform.localhost:8000/docs
- Health: http://apsilva-bed-data-platform.localhost:8000/health

## Endpoints

- `GET /health`
- `GET /databricks/jobs`
- `POST /databricks/jobs/{job_id}/run`
- `GET /databricks/run-history`
- `GET /data-ingestion/volumes`
- `GET /data-ingestion/upload-history`
- `POST /data-ingestion/volumes/{catalog_name}/{schema_name}/{volume_name}/files`

Parâmetros de query em `/databricks/jobs`:

- `limit` (padrão: `25`, min: `1`, max: `100`)
- `offset` (padrão: `0`)
- `expand_tasks` (padrão: `false`)

Exemplo:

```bash
curl -s "http://apsilva-bed-data-platform.localhost:8000/databricks/jobs?limit=10&offset=0"
```

Disparar job sem parâmetros:

```bash
curl -s -X POST "http://apsilva-bed-data-platform.localhost:8000/databricks/jobs/123/run"
```

Disparar job com parâmetros:

```bash
curl -s -X POST "http://apsilva-bed-data-platform.localhost:8000/databricks/jobs/123/run" \
	-H "Content-Type: application/json" \
	-d '{"parameters":{"country":"br","mode":"full"}}'
```

Resposta:

```json
{
	"items": [
		{
			"job_id": 123,
			"settings": {
				"name": "daily-import"
			}
		}
	],
	"pagination": {
		"limit": 10,
		"offset": 0,
		"returned": 1,
		"has_more": false,
		"next_offset": null
	}
}
```

## Usar Vault local para token Databricks

No `.env`, configure:

```env
SECRET_BACKEND=vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=dev-root-token
VAULT_KV_MOUNT=secret
VAULT_SECRET_VALUE_KEY=value
DATABRICKS_TOKEN_SECRET_NAME=databricks_token
```

Grave o token no Vault:

```bash
curl -s \
	-H "X-Vault-Token: dev-root-token" \
	-H "Content-Type: application/json" \
	-X POST \
	-d '{"data":{"value":"<seu-databricks-token>"}}' \
	http://localhost:8200/v1/secret/data/databricks_token
```

## Testes

```bash
docker compose run --rm api pytest -q tests
```

## Parar

```bash
docker compose down
```