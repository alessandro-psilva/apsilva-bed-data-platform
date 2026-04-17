# Desenvolvimento

Guia técnico do projeto apsilva-bed-data-platform.

## Objetivo

Expor uma API FastAPI para listar jobs do Databricks usando SDK oficial e segredo via ambiente ou Vault local.

## Estrutura Atual

```text
apsilva-bed-data-platform/
|- app/
|  |- main.py
|  |- config.py
|  |- api/
|  |  |- router.py
|  |  \- endpoints/
|  |     |- health.py
|  |     \- databricks.py
|  \- services/
|     |- databricks.py
|     \- secrets.py
|- tests/
|  |- conftest.py
|  \- test_api.py
|- docker-compose.yml
|- Dockerfile
|- requirements.txt
|- .env.example
|- README.md
\- DEVELOPMENT.md
```

## Fluxo da Requisição

1. Cliente chama `GET /databricks/jobs`.
2. Endpoint em `app/api/endpoints/databricks.py` valida query params.
3. Serviço em `app/services/databricks.py` resolve credencial.
4. Serviço chama `WorkspaceClient` do SDK Databricks.
5. Resposta é normalizada para contrato com `items` + `pagination`.

## Configuração

1. Criar `.env`:

```bash
cp .env.example .env
```

2. Variáveis essenciais:

- `DATABRICKS_WORKSPACE_NAME`
- `DATABRICKS_WORKSPACE`
- `DATABRICKS_TOKEN` (modo env)
- ou `SECRET_BACKEND=vault` + `DATABRICKS_TOKEN_SECRET_NAME` (modo vault)

## Execução Local

```bash
docker compose up --build
```

Links:

- API: http://apsilva-bed-data-platform.localhost:8000
- Swagger: http://apsilva-bed-data-platform.localhost:8000/docs

## Testes

```bash
docker compose run --rm api pytest -q tests
```

## Convenções

- Endpoints finos: regras no serviço.
- Configuração somente por ambiente.
- Tokens nunca hardcoded em código.
- Qualquer mudança em contrato de API deve atualizar testes e README.