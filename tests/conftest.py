import os


# Keep tests independent from external shell environment.
os.environ.setdefault("PROJECT_HOST", "apsilva-bed-data-platform.localhost")
os.environ.setdefault("PROJECT_PORT", "8000")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "warning")
