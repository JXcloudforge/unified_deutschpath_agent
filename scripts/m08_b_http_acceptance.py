"""Real loopback HTTP acceptance for M08-B rename-session confirmation/recovery."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def start_server(data_root: Path, port: int, log):
    env = os.environ.copy()
    env.update({
        "STAGE2_DATA_PATH": str(data_root),
        "STAGE2_EMBEDDING_PROVIDER": "deterministic",
        "STAGE3_ROUTER": "rules",
        "APP_ENV": "development",
        "M08_LOCAL_ENABLED": "true",
        "DEEPSEEK_API_KEY": "",
        "TAVILY_API_KEY": "",
    })
    return subprocess.Popen(
        [sys.executable, "scripts/mcp_b6_uvicorn_runner.py", "--host", "127.0.0.1", "--port", str(port)],
        cwd=PROJECT_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def stop_server(process):
    if process.poll() is None:
        try:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        except (AttributeError, OSError, ValueError):
            process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_ready(client, process):
    deadline = time.monotonic() + 35
    while time.monotonic() < deadline and process.poll() is None:
        try:
            response = client.get("/health")
            if response.status_code == 200 and response.json().get("m08_local_orchestration"):
                return response
        except httpx.HTTPError:
            time.sleep(0.25)
    raise RuntimeError("M08 Uvicorn did not become ready")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="deutschpath-m08b-") as temp:
        data_root = Path(temp) / "data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        log_path = Path(temp) / "uvicorn.log"
        log = log_path.open("w", encoding="utf-8")
        process = start_server(data_root, port, log)
        report = {"server": "loopback uvicorn", "initial_pid": process.pid}
        try:
            with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
                health = wait_ready(client, process)
                headers = {"X-User-ID": "m08b-" + uuid4().hex}
                created = client.post("/sessions", headers=headers)
                created.raise_for_status()
                session_id = created.json()["id"]

                ordinary = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                       json={"content": "Hallo"})
                ordinary.raise_for_status()
                if "orchestration" in ordinary.json():
                    raise RuntimeError("ordinary chat was incorrectly intercepted by M08")

                missing = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                      json={"content": "把当前会话改名"})
                missing.raise_for_status()
                first_op = missing.json()["orchestration"]
                if first_op["status"] != "NEEDS_CLARIFICATION":
                    raise RuntimeError("missing title did not enter clarification")
                clarified = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                        json={"content": "Deutsch draft"})
                clarified.raise_for_status()
                op_id = clarified.json()["orchestration"]["orchestration_id"]
                if op_id != first_op["orchestration_id"] or clarified.json()["orchestration"]["status"] != "AWAITING_CONFIRMATION":
                    raise RuntimeError("clarification did not continue the original proposal")
                revised = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                      json={"content": "改成 Deutsch final"})
                revised.raise_for_status()
                if revised.json()["orchestration"]["orchestration_id"] != op_id:
                    raise RuntimeError("edited proposal was detached from its orchestration")

                foreign = client.post(f"/sessions/{session_id}/messages", headers={"X-User-ID": "other-user"},
                                      json={"content": "确认"})
                if foreign.status_code != 404:
                    raise RuntimeError("cross-user session access was not rejected")

            stop_server(process)
            log.flush()
            process = start_server(data_root, port, log)
            report["restart_pid"] = process.pid
            with httpx.Client(base_url=base, timeout=30, trust_env=False) as client:
                wait_ready(client, process)
                confirmed = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                        json={"content": "确认"})
                confirmed.raise_for_status()
                result = confirmed.json()["orchestration"]
                if result["status"] != "SUCCEEDED":
                    raise RuntimeError(f"rename did not verify after restart: {result}")
                sessions = client.get("/sessions", headers=headers)
                sessions.raise_for_status()
                title = next(item["title"] for item in sessions.json() if item["id"] == session_id)
                if title != "Deutsch final":
                    raise RuntimeError("Conversation Query did not return the renamed title")
                replay = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                     json={"content": "确认"})
                replay.raise_for_status()
                if "没有再次执行" not in replay.json()["assistant_message"]["content"]:
                    raise RuntimeError("duplicate confirmation was not acknowledged idempotently")
                unsupported = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                          json={"content": "请创建两个德语学习任务"})
                unsupported.raise_for_status()
                if "没有执行操作" not in unsupported.json()["assistant_message"]["content"]:
                    raise RuntimeError("unsupported business write was not rejected explicitly")
                history = client.get(f"/sessions/{session_id}/messages", headers=headers)
                history.raise_for_status()
                report.update({
                    "health": health.status_code,
                    "ordinary_chat": ordinary.status_code,
                    "clarification": missing.status_code,
                    "confirmation_after_restart": confirmed.status_code,
                    "duplicate_confirmation": replay.status_code,
                    "cross_user": foreign.status_code,
                    "verified_title": title,
                    "history_count": len(history.json()),
                    "unsupported_write": "rejected_without_execution",
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
