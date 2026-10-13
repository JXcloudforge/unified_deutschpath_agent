"""Small acceptance-only Uvicorn runner with a graceful Windows stop signal."""
from __future__ import annotations

import argparse
import signal
from pathlib import Path
import sys

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    server = uvicorn.Server(uvicorn.Config("app.api.main:app", host=args.host, port=args.port, log_level="info"))
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, lambda *_: setattr(server, "should_exit", True))
    server.run()


if __name__ == "__main__":
    main()
