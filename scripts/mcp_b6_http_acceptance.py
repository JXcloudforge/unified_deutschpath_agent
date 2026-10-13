"""Real loopback acceptance for OCR -> human approval -> Database MCP -> chat history."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import socket
from uuid import uuid4

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ocr" / "vocabulary_table.png"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="deutschpath-b6-") as work:
        data_root = Path(work) / "data"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env = os.environ.copy()
        env.update({"STAGE2_DATA_PATH": str(data_root), "MCP_DATABASE_PATH": str(data_root / "mcp_business.sqlite3"),
                    "STAGE2_EMBEDDING_PROVIDER": "deterministic", "STAGE3_ROUTER": "rules", "DEEPSEEK_API_KEY": ""})
        log_path = Path(work) / "uvicorn.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "scripts/mcp_b6_uvicorn_runner.py", "--host", "127.0.0.1", "--port", str(port)],
                                       cwd=PROJECT_ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        base = f"http://127.0.0.1:{port}"
        report: dict = {"uvicorn_server": "real uvicorn.Server subprocess", "uvicorn_pid": process.pid}
        try:
            with httpx.Client(base_url=base, timeout=45, trust_env=False) as client:
                deadline = time.monotonic() + 30
                health = None
                while time.monotonic() < deadline and process.poll() is None:
                    try:
                        health = client.get("/health")
                        if health.is_success:
                            break
                    except httpx.HTTPError:
                        time.sleep(0.25)
                if health is None or health.status_code != 200:
                    raise RuntimeError("Uvicorn health did not become ready")
                headers = {"X-User-ID": "b6-http-" + uuid4().hex}
                session = client.post("/sessions", headers=headers)
                session.raise_for_status()
                session_id = session.json()["id"]
                uploaded = client.post(f"/sessions/{session_id}/ocr/images", headers=headers,
                                       files={"file": ("vocabulary_table.png", FIXTURE.read_bytes(), "image/png")})
                uploaded.raise_for_status()
                image_id = uploaded.json()["image_id"]
                ocr_message = client.post(f"/sessions/{session_id}/messages", headers=headers,
                                          json={"content": "请识别这张英语和德语单词表图片"})
                ocr_message.raise_for_status()
                response_body = ocr_message.json()
                if "tool_operation" not in response_body:
                    raise RuntimeError(f"natural-language MCP planner did not return a tool operation: {response_body}")
                candidate = response_body["tool_operation"]
                if candidate["status"] != "awaiting_confirmation" or len(candidate["rows"]) != 3:
                    raise RuntimeError("OCR candidate did not match expected reviewable table")
                business_db = data_root / "mcp_business.sqlite3"
                if business_db.exists():
                    raise RuntimeError("business database/schema appeared before explicit confirmation")
                denied = client.post(f"/sessions/{session_id}/ocr/confirm", headers={"X-User-ID": "b6-other"},
                                     json={"operation_id": candidate["operation_id"], "rows": candidate["rows"], "confirmed": True})
                if denied.status_code != 404:
                    raise RuntimeError("cross-user confirmation was not rejected")
                confirmed = client.post(f"/sessions/{session_id}/ocr/confirm", headers=headers,
                                        json={"operation_id": candidate["operation_id"], "rows": candidate["rows"], "confirmed": True})
                confirmed.raise_for_status()
                result = confirmed.json()
                history = client.get(f"/sessions/{session_id}/messages", headers=headers)
                history.raise_for_status()
                if result.get("status") != "verified" or result.get("inserted_rows") != 3:
                    raise RuntimeError("Database MCP did not return verified write")
                if not any(item["role"] == "assistant" and "verified" in item["content"] for item in history.json()):
                    raise RuntimeError("verified Agent response was not persisted to chat history")
                report.update({"health_status": health.status_code, "session_status": session.status_code,
                               "upload_status": uploaded.status_code, "ocr_message_status": ocr_message.status_code,
                               "rows_before_confirmation": 0, "cross_user_status": denied.status_code,
                               "confirm_status": confirmed.status_code, "database_status": result["status"],
                               "inserted_rows": result["inserted_rows"], "history_messages": len(history.json())})
        finally:
            if process.poll() is None:
                try:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                except (AttributeError, OSError, ValueError):
                    process.terminate()
            try:
                process.wait(timeout=20)
                report["shutdown"] = "graceful"
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                report["shutdown"] = "forced"
        report["uvicorn_startup_complete"] = "Application startup complete" in log_path.read_text(encoding="utf-8", errors="replace")
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if report.get("shutdown") != "graceful" or not report.get("uvicorn_startup_complete"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
