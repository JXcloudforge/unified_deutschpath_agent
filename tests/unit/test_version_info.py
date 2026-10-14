import json
from copy import deepcopy

import pytest

from ui.version_info import MANIFEST_FILE, _read_manifest, load_version_information


def test_version_information_is_manifest_driven_and_contains_ten_milestones():
    info = load_version_information()
    assert info["app_name"] == "Deutschpath Unified Agent"
    assert info["version"] == "v0.1.1.dev0"
    assert info["status"] == "unreleased development candidate"
    assert "Maintenance" in info["latest_summary"]
    assert "NOT VERIFIED" in info["features"]
    assert [item["version"] for item in info["releases"]] == ["0.1.1.dev0", "0.1.0-beta.1"]
    assert [item["id"] for item in info["milestones"]] == [f"M{i:02d}" for i in range(1, 11)]
    assert MANIFEST_FILE == "docs/iterations/manifest.json"
    assert all(item["features"] and item["technology"] and item["chain"] and item["problem"]
               for item in info["milestones"])


def test_manifest_rejects_documents_outside_controlled_directories(monkeypatch, tmp_path):
    from ui import version_info

    manifest = json.loads((version_info.PROJECT_ROOT / MANIFEST_FILE).read_text(encoding="utf-8"))
    manifest = deepcopy(manifest)
    manifest["milestones"][0]["document"] = "../../.env"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(version_info, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(version_info, "MANIFEST_FILE", "manifest.json")
    with pytest.raises(ValueError, match="outside the controlled iteration directory"):
        _read_manifest()
