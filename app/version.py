"""Single source for the source-checkout application version."""

from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]
with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
    VERSION = tomllib.load(project_file)["project"]["version"]

DISPLAY_VERSION = f"v{VERSION}"
