"""Validate the selected project interpreter before launching an entry point."""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

REQUIRED_MODULES = {
    "backend": (
        "fastapi", "uvicorn", "chromadb", "httpx", "mcp", "pydantic",
        "dotenv", "pypdf", "docx", "multipart", "rapidocr",
        "onnxruntime", "sentence_transformers",
    ),
    "frontend": ("streamlit", "requests", "httpx", "dotenv"),
}


def version_satisfies(specifier: str, version: tuple[int, int]) -> bool:
    operators = {
        ">=": lambda actual, expected: actual >= expected,
        ">": lambda actual, expected: actual > expected,
        "<=": lambda actual, expected: actual <= expected,
        "<": lambda actual, expected: actual < expected,
        "==": lambda actual, expected: actual == expected,
    }
    for clause in specifier.split(","):
        match = re.fullmatch(r"\s*(>=|>|<=|<|==)\s*(\d+)\.(\d+)\s*", clause)
        if match is None:
            return False
        operator, major, minor = match.groups()
        if not operators[operator](version, (int(major), int(minor))):
            return False
    return True


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"backend", "frontend"}:
        print("Usage: check_runtime.py backend|frontend", file=sys.stderr)
        return 2

    project_root = Path(__file__).resolve().parents[1]
    try:
        project = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"Cannot read project Python requirements: {exc}", file=sys.stderr)
        return 1

    required = project.get("project", {}).get("requires-python", "")
    if not version_satisfies(required, sys.version_info[:2]):
        print(f"Python {sys.version.split()[0]} does not satisfy requires-python: {required}", file=sys.stderr)
        return 1

    modules = REQUIRED_MODULES[sys.argv[1]]
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    print(f"Python {sys.version.split()[0]}; missing modules: {', '.join(missing) if missing else 'none'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
