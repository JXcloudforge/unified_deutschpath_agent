from app.version import DISPLAY_VERSION, VERSION


def test_project_version_is_the_single_candidate_version():
    assert VERSION == "0.2.1"
    assert DISPLAY_VERSION == "v0.2.1"
