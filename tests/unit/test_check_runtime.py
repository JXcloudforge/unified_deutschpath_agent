from scripts.check_runtime import REQUIRED_MODULES, version_satisfies


def test_project_python_constraint_is_checked():
    assert version_satisfies(">=3.14,<3.15", (3, 14))
    assert not version_satisfies(">=3.14,<3.15", (3, 12))


def test_launcher_checks_dependencies_needed_by_each_entry_point():
    assert {"fastapi", "uvicorn", "chromadb", "mcp", "rapidocr", "onnxruntime"} <= set(REQUIRED_MODULES["backend"])
    assert {"streamlit", "requests"} <= set(REQUIRED_MODULES["frontend"])
