import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[2]


def test_bilingual_readme_links_resolve_inside_repository():
    for readme_name in ("README.md", "README.en.md"):
        content = (ROOT / readme_name).read_text(encoding="utf-8")
        assert "README.en.md" in content if readme_name == "README.md" else "README.md" in content
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", content):
            target = target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("https://", "http://", "mailto:", "#")):
                continue
            local_target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            assert (ROOT / local_target).is_file(), f"{readme_name} links to missing file: {target}"
