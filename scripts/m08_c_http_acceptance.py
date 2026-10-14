"""Real loopback HTTP acceptance for the bounded M08-C rename-then-list plan."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import uuid

import httpx

from m08_b_http_acceptance import start_server, stop_server, wait_ready


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="deutschpath-m08c-") as temp:
        root = Path(temp)
        data_root, log_path = root / "data", root / "uvicorn.log"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base_url = f"http://127.0.0.1:{port}"
        log = log_path.open("w", encoding="utf-8")
        process = start_server(data_root, port, log)
        report = {"server": "loopback uvicorn", "first_pid": process.pid}
        try:
            with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as client:
                wait_ready(client, process)
                headers = {"X-User-ID": "m08c-" + uuid.uuid4().hex}
                created = client.post("/sessions", headers=headers)
                created.raise_for_status()
                session_id = created.json()["id"]

                request = client.post(f"/sessions/{session_id}/messages", headers=headers,
                    json={"content": "先把当前会话改名为Deutschpath产品演示，然后列出我的会话"})
                request.raise_for_status()
                plan = request.json()["orchestration"]
                if plan["status"] != "AWAITING_CONFIRMATION":
                    raise RuntimeError("multi-step plan was not held for explicit confirmation")
                if [step["action_type"] for step in plan["steps"]] != ["rename_session", "list_sessions"]:
                    raise RuntimeError("the confirmed plan did not contain exactly the supported two actions")
                if plan["steps"][1]["depends_on"] != ["rename-session"]:
                    raise RuntimeError("list_sessions is not dependent on rename success")

                before = client.get("/sessions", headers=headers)
                before.raise_for_status()
                if next(item["title"] for item in before.json() if item["id"] == session_id) == "Deutschpath产品演示":
                    raise RuntimeError("the Command ran before confirmation")

            stop_server(process)
            process = start_server(data_root, port, log)
            report["restart_pid"] = process.pid
            with httpx.Client(base_url=base_url, timeout=30, trust_env=False) as client:
                wait_ready(client, process)
                confirmed = client.post(f"/sessions/{session_id}/messages", headers=headers,
                    json={"content": "确认"})
                confirmed.raise_for_status()
                body = confirmed.json()
                if body["orchestration"]["status"] != "SUCCEEDED":
                    raise RuntimeError(f"confirmed plan did not complete: {body}")
                steps = body["orchestration"]["steps"]
                if [step["status"] for step in steps] != ["SUCCEEDED", "SUCCEEDED"]:
                    raise RuntimeError(f"step results were incomplete: {steps}")
                listing = json.loads(steps[1]["result_reference"])
                if not any(item["title"] == "Deutschpath产品演示" for item in listing):
                    raise RuntimeError("Query result did not include the renamed session")
                answer = body["assistant_message"]["content"]
                if "Deutschpath产品演示" not in answer or "当前会话列表" not in answer:
                    raise RuntimeError("assistant response did not report both completed steps")

                sessions = client.get("/sessions", headers=headers)
                sessions.raise_for_status()
                persisted_title = next(item["title"] for item in sessions.json() if item["id"] == session_id)
                if persisted_title != "Deutschpath产品演示":
                    raise RuntimeError("Conversation Query did not verify persisted rename")
                replay = client.post(f"/sessions/{session_id}/messages", headers=headers,
                    json={"content": "确认"})
                replay.raise_for_status()
                if "没有再次执行" not in replay.json()["assistant_message"]["content"]:
                    raise RuntimeError("duplicate confirmation did not remain idempotent")
                report.update({
                    "proposal_status": plan["status"],
                    "restart_confirmation": confirmed.status_code,
                    "steps": [step["action_type"] + ":" + step["status"] for step in steps],
                    "verified_title": persisted_title,
                    "query_result_count": len(listing),
                    "duplicate_confirmation": replay.status_code,
                })
        finally:
            stop_server(process)
            log.flush()
            log.close()
        report["startup_complete"] = "Application startup complete" in log_path.read_text(encoding="utf-8", errors="replace")
        print(json.dumps(report, ensure_ascii=True, sort_keys=True))
        return 0 if report["startup_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
