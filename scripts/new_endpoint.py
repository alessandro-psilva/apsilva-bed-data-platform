#!/usr/bin/env python3
from __future__ import annotations

import argparse
import keyword
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent

MODULE_NAME_RE = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class ProjectPaths:
    repo_root: Path
    endpoints_dir: Path
    schemas_dir: Path
    tests_dir: Path
    router_path: Path


def get_project_paths() -> ProjectPaths:
    repo_root = Path(__file__).resolve().parents[1]
    return ProjectPaths(
        repo_root=repo_root,
        endpoints_dir=repo_root / "app" / "api" / "endpoints",
        schemas_dir=repo_root / "app" / "schemas",
        tests_dir=repo_root / "tests" / "endpoints",
        router_path=repo_root / "app" / "api" / "router.py",
    )


def to_pascal_case(value: str) -> str:
    parts = re.split(r"[_\-\s]+", value.strip())
    return "".join(part.capitalize() for part in parts if part)


def singularize(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("s") and len(value) > 1:
        return value[:-1]
    return value


def build_schema_content(module_name: str) -> str:
    base = to_pascal_case(singularize(module_name))
    return dedent(
        f"""\
        from pydantic import BaseModel


        class {base}Create(BaseModel):
            name: str


        class {base}Response(BaseModel):
            id: int
            name: str
        """
    )


def build_endpoint_content(module_name: str, with_schema: bool) -> str:
    fn_suffix = module_name
    if with_schema:
        base = to_pascal_case(singularize(module_name))
        return dedent(
            f"""\
            from fastapi import APIRouter

            from app.schemas.{module_name} import {base}Create, {base}Response


            router = APIRouter()


            @router.get("")
            def list_{fn_suffix}() -> dict[str, str]:
                return {{"endpoint": "{module_name}", "message": "ok"}}


            @router.post("", response_model={base}Response)
            def create_{singularize(fn_suffix)}(payload: {base}Create) -> {base}Response:
                return {base}Response(id=1, name=payload.name)
            """
        )

    return dedent(
        f"""\
        from fastapi import APIRouter


        router = APIRouter()


        @router.get("")
        def list_{fn_suffix}() -> dict[str, str]:
            return {{"endpoint": "{module_name}", "message": "ok"}}
        """
    )


def build_test_content(module_name: str, prefix: str, with_schema: bool) -> str:
    endpoint_path = prefix
    if with_schema:
        return dedent(
            f"""\
            from fastapi.testclient import TestClient

            from app.main import app


            client = TestClient(app)


            def test_list_{module_name}() -> None:
                response = client.get("{endpoint_path}")
                assert response.status_code == 200


            def test_create_{singularize(module_name)}() -> None:
                response = client.post("{endpoint_path}", json={{"name": "demo"}})
                assert response.status_code == 200
                body = response.json()
                assert body["name"] == "demo"
            """
        )

    return dedent(
        f"""\
        from fastapi.testclient import TestClient

        from app.main import app


        client = TestClient(app)


        def test_list_{module_name}() -> None:
            response = client.get("{endpoint_path}")
            assert response.status_code == 200
        """
    )


def validate_module_name(module_name: str) -> str:
    normalized = module_name.strip().lower().replace("-", "_")
    if not MODULE_NAME_RE.fullmatch(normalized):
        raise argparse.ArgumentTypeError(
            "Nome invalido. Use apenas letras minusculas, numeros e underscore."
        )
    if keyword.iskeyword(normalized):
        raise argparse.ArgumentTypeError(
            f"Nome invalido: '{normalized}' e palavra reservada do Python."
        )
    return normalized


def ensure_project_layout(paths: ProjectPaths) -> None:
    if not paths.endpoints_dir.exists() or not paths.router_path.exists():
        raise RuntimeError(
            "Estrutura base nao encontrada. Execute o script dentro do projeto."
        )


def insert_after_last_match(lines: list[str], prefix: str, new_line: str) -> list[str]:
    if new_line in lines:
        return lines

    insert_at = -1
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            insert_at = index

    if insert_at >= 0:
        lines.insert(insert_at + 1, new_line)
        return lines

    raise RuntimeError(f"Nao foi possivel localizar bloco com prefixo: {prefix}")


def build_router_content(current_content: str, module_name: str, prefix: str, tag: str) -> str:
    import_line = f"from app.api.endpoints.{module_name} import router as {module_name}_router"
    include_line = (
        f"api_router.include_router({module_name}_router, prefix=\"{prefix}\", tags=[\"{tag}\"])"
    )

    lines = current_content.splitlines()

    try:
        lines = insert_after_last_match(lines, "from app.api.endpoints.", import_line)
    except RuntimeError:
        lines = insert_after_last_match(lines, "from fastapi", import_line)

    lines = insert_after_last_match(lines, "api_router.include_router(", include_line)
    return "\n".join(lines) + "\n"


def update_router(router_path: Path, module_name: str, prefix: str, tag: str) -> None:
    current_content = router_path.read_text(encoding="utf-8")
    updated_content = build_router_content(current_content, module_name, prefix, tag)
    router_path.write_text(updated_content, encoding="utf-8")


def print_dry_run(
    module_name: str,
    endpoint_path: Path,
    schema_path: Path,
    test_path: Path,
    endpoint_content: str,
    schema_content: str | None,
    test_content: str,
    router_content: str,
) -> None:
    print("[dry-run] Nenhum arquivo foi alterado.")
    print(f"[dry-run] Criaria: {endpoint_path}")
    print("\n--- app/api/endpoints/{name}.py ---".format(name=module_name))
    print(endpoint_content.rstrip())

    if schema_content is not None:
        print(f"\n[dry-run] Criaria: {schema_path}")
        print("\n--- app/schemas/{name}.py ---".format(name=module_name))
        print(schema_content.rstrip())

    print(f"\n[dry-run] Criaria: {test_path}")
    print("\n--- tests/endpoints/test_{name}.py ---".format(name=module_name))
    print(test_content.rstrip())

    print("\n[dry-run] Atualizaria: app/api/router.py")
    print("\n--- app/api/router.py (preview) ---")
    print(router_content.rstrip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera estrutura de endpoint e registra no app/api/router.py"
    )
    parser.add_argument(
        "name",
        type=validate_module_name,
        help="Nome do modulo do endpoint. Ex: users",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Prefixo da rota. Ex: /users (padrao: /<name>)",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Tag do Swagger (padrao: <name>)",
    )
    parser.add_argument(
        "--with-schema",
        action="store_true",
        help="Tambem cria schema em app/schemas/<name>.py e adiciona POST de exemplo",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra arquivos e alteracoes sem gravar no disco",
    )
    args = parser.parse_args()

    module_name = args.name
    paths = get_project_paths()
    endpoint_path = paths.endpoints_dir / f"{module_name}.py"
    schema_path = paths.schemas_dir / f"{module_name}.py"
    test_path = paths.tests_dir / f"test_{module_name}.py"
    created_files: list[Path] = []
    original_router_content: str | None = None

    try:
        ensure_project_layout(paths)
        original_router_content = paths.router_path.read_text(encoding="utf-8")

        if endpoint_path.exists():
            raise FileExistsError(f"Endpoint ja existe em {endpoint_path}")

        if args.with_schema and schema_path.exists():
            raise FileExistsError(f"Schema ja existe em {schema_path}")

        if test_path.exists():
            raise FileExistsError(f"Teste ja existe em {test_path}")

        prefix = args.prefix or f"/{module_name}"
        tag = args.tag or module_name

        endpoint_content = build_endpoint_content(module_name, args.with_schema)
        schema_content = (
            build_schema_content(module_name) if args.with_schema else None
        )
        test_content = build_test_content(module_name, prefix, args.with_schema)
        router_preview = build_router_content(original_router_content, module_name, prefix, tag)

        if args.dry_run:
            print_dry_run(
                module_name=module_name,
                endpoint_path=endpoint_path,
                schema_path=schema_path,
                test_path=test_path,
                endpoint_content=endpoint_content,
                schema_content=schema_content,
                test_content=test_content,
                router_content=router_preview,
            )
            return 0

        paths.tests_dir.mkdir(parents=True, exist_ok=True)

        endpoint_path.write_text(endpoint_content, encoding="utf-8")
        created_files.append(endpoint_path)

        if args.with_schema:
            schema_path.write_text(schema_content, encoding="utf-8")
            created_files.append(schema_path)

        test_path.write_text(test_content, encoding="utf-8")
        created_files.append(test_path)

        update_router(paths.router_path, module_name, prefix, tag)

    except (FileExistsError, RuntimeError, OSError) as exc:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)

        if original_router_content is not None:
            paths.router_path.write_text(original_router_content, encoding="utf-8")

        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    print("Endpoint criado com sucesso.")
    print(f"- Endpoint: app/api/endpoints/{module_name}.py")
    if args.with_schema:
        print(f"- Schema: app/schemas/{module_name}.py")
    print(f"- Teste: tests/endpoints/test_{module_name}.py")
    print("- Router atualizado: app/api/router.py")
    print("Agora rode: docker compose up --build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
