"""Optional manual Tavily connectivity check; it is intentionally outside pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.web import TavilySearchProvider, WebSearchError


def main() -> int:
    provider = TavilySearchProvider()
    try:
        response = provider.search("Berlin weather", max_results=1)
    except WebSearchError as exc:
        print(f"Tavily live verification not completed: {exc}")
        return 1
    print(f"Tavily live verification succeeded: {len(response.results)} result(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
