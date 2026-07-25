"""Shared local configuration for the Playwright smoke-test scripts."""

import os
from pathlib import Path


def _load_env() -> dict[str, str]:
    values = {}
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


_env = _load_env()
_http_port = os.getenv("HTTP_PORT") or _env.get("HTTP_PORT") or "80"
_default_origin = (
    "http://localhost" if _http_port == "80" else f"http://localhost:{_http_port}"
)

BASE_URL = (os.getenv("ERP_BASE_URL") or f"{_default_origin}/erp").rstrip("/")
USERNAME = os.getenv("ERP_ADMIN_USERNAME") or _env.get("ADMIN_USERNAME") or "admin"
PASSWORD = os.getenv("ERP_ADMIN_PASSWORD") or _env.get("ADMIN_PASSWORD")

if not PASSWORD:
    raise RuntimeError(
        "Set ERP_ADMIN_PASSWORD or ADMIN_PASSWORD in .env before running browser tests."
    )
