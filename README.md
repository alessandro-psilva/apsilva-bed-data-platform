# apsilva-bed-fastapi-lab

Projeto backend-only com FastAPI, executado sempre com Docker.

Guia de desenvolvimento: ver `DEVELOPMENT.md`.

## Requisitos

- Docker
- Docker Compose

## Parametros do projeto

O projeto usa estes parametros em runtime:

- `PROJECT_HOST`
- `PROJECT_PORT`

Exemplo alterando os parametros sem editar codigo:

```bash
PROJECT_HOST=meu-lab.localhost PROJECT_PORT=8010 docker compose up --build
```

## Executar

```bash
docker compose up --build
```

## Host com nome do projeto

Use `apsilva-bed-fastapi-lab.localhost`. Esse dominio resolve localmente sem editar `/etc/hosts`.

## Acessos

- API: http://apsilva-bed-fastapi-lab.localhost:8000
- Docs Swagger: http://apsilva-bed-fastapi-lab.localhost:8000/docs
- Healthcheck: http://apsilva-bed-fastapi-lab.localhost:8000/health

## Endpoints disponíveis

- `GET /health`
- `GET /info`
- `POST /echo`

## Exemplos rápidos

```bash
curl -s http://apsilva-bed-fastapi-lab.localhost:8000/health
curl -s http://apsilva-bed-fastapi-lab.localhost:8000/info
curl -s -X POST http://apsilva-bed-fastapi-lab.localhost:8000/echo -H "Content-Type: application/json" -d '{"message":"hello"}'
```

## Parar

```bash
docker compose down
```