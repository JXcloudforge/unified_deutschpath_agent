"""Real loopback HTTP check for opt-in M09 suggestions and stored Chat history."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import uuid

import httpx

from m08_b_http_acceptance import start_server, stop_server, wait_ready


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="deutschpath-m09-") as temp:
        root = Path(temp)
        data_root, log_path = root / "data", root / "uvicorn.log"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        log = log_path.open("w", encoding="utf-8")
        process = start_server(data_root, port, log)
        report = {"server": "loopback uvicorn", "pid": process.pid}
        try:
            with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as client:
                wait_ready(client, process)
                headers = {"X-User-ID": "m09-" + uuid.uuid4().hex}
                created = client.post("/sessions", headers=headers)
                created.raise_for_status()
                session_id = created.json()["id"]
                question = "德国 Ausbildung 对德语水平有什么要求？"

                legacy = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                     json={"content": question})
                legacy.raise_for_status()
                if "suggestions" in legacy.json():
                    raise RuntimeError("suggestions were not opt-in")

                enabled = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                      json={"content": question, "include_suggestions": True})
                enabled.raise_for_status()
                body = enabled.json()
                suggestions = body.get("suggestions")
                if not isinstance(suggestions, list) or not 1 <= len(suggestions) <= 3:
                    raise RuntimeError(f"expected 1 to 3 suggestions, received {suggestions!r}")
                if suggestions[0].get("category") != "ausbildung":
                    raise RuntimeError("suggestion topic did not match the current Ausbildung question")

                history = client.get(f"/sessions/{session_id}/messages", headers=headers)
                history.raise_for_status()
                if len(history.json()) != 4:
                    raise RuntimeError("M09 wrote unexpected extra Conversation messages")
                foreign = client.get(f"/sessions/{session_id}/messages", headers={"X-User-ID": "other-user"})
                if foreign.status_code != 404:
                    raise RuntimeError("cross-user history access was not rejected")
                report.update({
                    "opt_in_suggestions": len(suggestions),
                    "category": suggestions[0]["category"],
                    "history_messages": len(history.json()),
                    "cross_user_status": foreign.status_code,
                    "old_response_compatible": True,
                })
        finally:
            stop_server(process)
            log.flush()
            log.close()
        report["startup_complete"] = "Application startup complete" in log_path.read_text(encoding="utf-8", errors="replace")
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if not report["startup_complete"]:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
