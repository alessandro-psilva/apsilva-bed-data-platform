# Desenvolvimento

Este documento explica a estrutura do projeto, a responsabilidade de cada pasta e como evoluir o lab com novos endpoints no FastAPI usando Docker.

## Objetivo do projeto

Este repositório e um lab simples para aprender FastAPI com execucao docker-first.

Principios deste lab:

- Simples de entender
- Rapido para subir
- Facil de evoluir por modulos

## Estrutura de pastas

```text
apsilva-bed-fastapi-lab/
|- app/
|  |- main.py
|  |- api/
|  |  |- router.py
|  |  \- endpoints/
|  |     |- health.py
|  |     |- info.py
|  |     \- echo.py
|  \- schemas/
|     \- echo.py
|- Dockerfile
|- docker-compose.yml
|- requirements.txt
|- README.md
\- DEVELOPMENT.md
```

### O que e cada pasta/arquivo

- `app/`: codigo da aplicacao FastAPI.
- `app/main.py`: ponto de entrada da API; cria o objeto FastAPI e inclui o roteador principal.
- `app/api/router.py`: roteador central; registra todos os modulos de endpoint.
- `app/api/endpoints/`: endpoints organizados por dominio/assunto.
- `app/schemas/`: modelos Pydantic para entrada/saida dos endpoints.
- `Dockerfile`: imagem da aplicacao Python + FastAPI.
- `docker-compose.yml`: orquestracao local do servico API.
- `requirements.txt`: dependencias Python.
- `README.md`: uso rapido do projeto.
- `DEVELOPMENT.md`: guia de desenvolvimento e evolucao.

## Como a requisicao flui

1. Cliente chama um endpoint HTTP.
2. FastAPI recebe em `app/main.py`.
3. `main.py` delega para `app/api/router.py`.
4. `router.py` direciona para o modulo em `app/api/endpoints/`.
5. Endpoint valida entrada/saida usando schemas em `app/schemas/` quando necessario.

## Como subir o projeto

Fluxo oficial deste lab: execucao via Docker Compose.

```bash
docker compose up --build
```

Links uteis:

- API: http://apsilva-bed-fastapi-lab.localhost:8000
- Swagger: http://apsilva-bed-fastapi-lab.localhost:8000/docs
- ReDoc: http://apsilva-bed-fastapi-lab.localhost:8000/redoc

Parar:

```bash
docker compose down
```

## Como criar um novo endpoint

Exemplo: criar modulo `users`.

### Opcao automatica (script)

Voce pode gerar endpoint e registro no router com um comando:

```bash
python3 scripts/new_endpoint.py users
```

Esse comando tambem cria scaffold de teste em `tests/endpoints/test_users.py`.

Com schema + POST de exemplo:

```bash
python3 scripts/new_endpoint.py users --with-schema
```

Preview sem gravar em disco:

```bash
python3 scripts/new_endpoint.py users --with-schema --dry-run
```

Opcoes extras:

- `--prefix /clientes`
- `--tag clientes`

Depois execute:

```bash
docker compose up --build
```

## Testes

Rodar testes no fluxo oficial (Docker Compose):

```bash
docker compose run --rm api pytest -q tests
```

### Opcao manual

1. Criar schema (se houver payload):

Arquivo: `app/schemas/user.py`

```python
from pydantic import BaseModel


class UserCreate(BaseModel):
    name: str


class UserResponse(BaseModel):
    id: int
    name: str
```

2. Criar endpoint:

Arquivo: `app/api/endpoints/users.py`

```python
from fastapi import APIRouter

from app.schemas.user import UserCreate, UserResponse


router = APIRouter()


@router.post("", response_model=UserResponse)
def create_user(payload: UserCreate) -> UserResponse:
    return UserResponse(id=1, name=payload.name)
```

3. Registrar no roteador principal:

Arquivo: `app/api/router.py`

```python
from app.api.endpoints.users import router as users_router

api_router.include_router(users_router, prefix="/users", tags=["users"])
```

4. Rebuild e testar:

```bash
docker compose up --build
curl -s -X POST http://apsilva-bed-fastapi-lab.localhost:8000/users -H "Content-Type: application/json" -d '{"name":"Ana"}'
```

## Convencoes recomendadas

- Um arquivo por dominio em `app/api/endpoints/`.
- Prefixos curtos e consistentes (`/users`, `/orders`, `/reports`).
- Sempre usar schema para request/response quando houver payload.
- Nomes claros para funcoes de endpoint (`create_user`, `list_users`).
- Evitar logica pesada dentro do endpoint; mover para camada de servico quando crescer.

## Como evoluir sem perder simplicidade

Evolucao sugerida em fases:

1. Fase 1: endpoints simples sem banco (estado em memoria, apenas para aprender).
2. Fase 2: adicionar camada `services/` para regras de negocio.
3. Fase 3: adicionar banco e persistencia (`SQLAlchemy` + migracoes).
4. Fase 4: adicionar testes automatizados (`pytest`) e lint (`ruff`).
5. Fase 5: separar configuracoes por ambiente (dev, test, prod).

Quando criar novas pastas:

- `app/services/`: regras de negocio reutilizaveis.
- `app/repositories/`: acesso a dados.
- `tests/`: testes de endpoint e regras.

## Erros comuns

- Esquecer de registrar router no `app/api/router.py`.
- Misturar validacao de payload com regra de negocio no mesmo bloco.
- Criar endpoints sem schema e perder validacao/documentacao.
- Fazer alteracao e nao rebuildar quando necessario (`docker compose up --build`).

## Checklist para novo endpoint

- Criou ou atualizou schema em `app/schemas/`.
- Criou modulo em `app/api/endpoints/`.
- Registrou no `app/api/router.py`.
- Testou no Swagger.
- Testou com curl.
- Atualizou README se endpoint for relevante para consumo.