"""Load repository-controlled release and iteration notes for the local UI."""

import json
from pathlib import Path
from typing import Any

from app.version import DISPLAY_VERSION, PROJECT_ROOT


MANIFEST_FILE = "docs/iterations/manifest.json"
CHANGELOG_FILE = "docs/CHANGELOG.md"
FEATURES_FILE = "docs/FEATURES.md"


def _read_manifest() -> dict[str, Any]:
    path = PROJECT_ROOT / MANIFEST_FILE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("iteration manifest schema is not supported")
    milestones = payload.get("milestones")
    releases = payload.get("releases")
    if not isinstance(milestones, list) or not isinstance(releases, list):
        raise ValueError("iteration manifest is missing required lists")
    for milestone in milestones:
        if not isinstance(milestone, dict) or not all(
            isinstance(milestone.get(key), str) and milestone[key].strip()
            for key in ("id", "title", "summary", "status", "document")
        ):
            raise ValueError("iteration manifest contains an invalid milestone")
        document = milestone["document"]
        if not document.startswith("docs/iterations/") or not document.endswith(".md") or ".." in Path(document).parts:
            raise ValueError("milestone document path is outside the controlled iteration directory")
        for key in ("problem", "chain"):
            if not isinstance(milestone.get(key), str) or not milestone[key].strip():
                raise ValueError(f"milestone is missing {key}")
        for key in ("features", "technology"):
            values = milestone.get(key)
            if not isinstance(values, list) or not values or not all(isinstance(value, str) and value.strip() for value in values):
                raise ValueError(f"milestone has invalid {key}")
        resolved_document = (PROJECT_ROOT / document).resolve()
        if not resolved_document.is_relative_to((PROJECT_ROOT / "docs/iterations").resolve()) or not resolved_document.is_file():
            raise ValueError("milestone document is missing or outside the controlled iteration directory")
    for release in releases:
        if not isinstance(release, dict) or not all(
            isinstance(release.get(key), str) and release[key].strip()
            for key in ("version", "status", "document")
        ):
            raise ValueError("iteration manifest contains an invalid release")
        document = release["document"]
        if not document.startswith("docs/releases/") or not document.endswith(".md") or ".." in Path(document).parts:
            raise ValueError("release document path is outside the controlled release directory")
    if [item["id"] for item in milestones] != [f"M{i:02d}" for i in range(1, 11)]:
        raise ValueError("iteration manifest must define milestones M01 through M10 in order")
    if len({item["version"] for item in releases}) != len(releases):
        raise ValueError("iteration manifest contains duplicate release versions")
    return payload


def _latest_changelog_section(changelog: str) -> str:
    sections = changelog.split("\n## ")
    return "## " + sections[1] if len(sections) > 1 else changelog


def load_version_information() -> dict[str, object]:
    """Read only fixed documentation plus paths validated from the local manifest."""
    manifest = _read_manifest()
    changelog = (PROJECT_ROOT / CHANGELOG_FILE).read_text(encoding="utf-8")
    features = (PROJECT_ROOT / FEATURES_FILE).read_text(encoding="utf-8")
    releases = []
    for item in manifest["releases"]:
        path = (PROJECT_ROOT / item["document"]).resolve()
        if not path.is_relative_to((PROJECT_ROOT / "docs/releases").resolve()):
            raise ValueError("release document escapes the controlled directory")
        releases.append({**item, "markdown": path.read_text(encoding="utf-8")})
    current = next((item for item in releases if item["version"] in DISPLAY_VERSION), None)
    return {
        "app_name": "Deutschpath Unified Agent",
        "version": DISPLAY_VERSION,
        "status": current["status"] if current else "当前版本的发布说明尚未建立",
        "latest_summary": _latest_changelog_section(changelog),
        "features": features,
        "releases": releases,
        "milestones": [
            item for item in manifest["milestones"]
        ],
    }
