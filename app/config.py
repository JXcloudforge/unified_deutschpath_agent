"""Process configuration bootstrap; load the project-local .env exactly once."""

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


# app/config.py → app/ → project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
PROCESS_ENV_AT_LOAD = frozenset(os.environ)


def load_project_env(env_file: Path | None = None) -> bool:
    """Load dotenv values without replacing values supplied by the host environment."""
    return load_dotenv(dotenv_path=env_file or ENV_FILE, override=False)


def setting_source(name: str, env_file: Path | None = None) -> str:
    """Return the winning configuration source without revealing its value."""
    if name in PROCESS_ENV_AT_LOAD:
        return "process environment"
    values = dotenv_values(env_file or ENV_FILE)
    if values.get(name) not in (None, ""):
        return ".env"
    return "not configured"


load_project_env()
