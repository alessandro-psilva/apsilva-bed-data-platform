import os


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
    return value


PROJECT_HOST = _required_env("PROJECT_HOST")
PROJECT_PORT = _required_env("PROJECT_PORT")


def get_base_url() -> str:
    return f"http://{PROJECT_HOST}:{PROJECT_PORT}"
