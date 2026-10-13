"""Run against an already-started local Uvicorn process; never targets production data."""

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx

BASE_URL = "http://127.0.0.1:8765"
HEADERS = {"X-User-ID": "http-acceptance-user"}


def check_crm(client: httpx.Client) -> dict:
    """Extend the existing real-HTTP acceptance with a fresh B2 test identity."""
    identity = f"b2-crm-{uuid4().hex}"
    headers = {"X-User-ID": identity}
    other = {"X-User-ID": f"{identity}-other"}
    empty = client.get("/users/me/state", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == dict(user_id=identity, current_level=None, target_level=None,
                               learning_goal=None, learning_preferences=None)
    profile = dict(current_level="A1", target_level="B1", learning_goal="Explain Dativ",
                   learning_preferences="Simple examples")
    updated = client.patch("/users/me/state", headers=headers, json=profile)
    assert updated.status_code == 200 and updated.json() == dict(user_id=identity, **profile)
    changed = client.patch("/users/me/state", headers=headers, json={"current_level": " a2 "})
    assert changed.status_code == 200 and changed.json()["current_level"] == "A2"
    assert changed.json()["target_level"] == "B1"
    cleared = client.patch("/users/me/state", headers=headers, json={"learning_preferences": None})
    assert cleared.status_code == 200 and cleared.json()["learning_preferences"] is None
    assert client.patch("/users/me/state", headers=headers, json=profile).status_code == 200
    for invalid in ({}, {"current_level": "B9"}, {"learning_goal": " "},
                    {"learning_preferences": []}, {"user_id": "other"}, {"learning_goal": "x" * 2001}):
        assert client.patch("/users/me/state", headers=headers, json=invalid).status_code == 422
    for path in ("/users/me/state", "/users/me/events"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-User-ID": ""}).status_code == 401
    assert client.get("/users/me/state", headers=other).json()["current_level"] is None
    event_ids = []
    for item in ("Dativ lesson", "Dativ practice"):
        saved = client.post("/users/me/events", headers=headers,
                            json={"event_type": "practice", "item": item, "result": "completed"})
        assert saved.status_code == 201
        event_ids.append(saved.json()["id"])
    events = client.get("/users/me/events", headers=headers).json()
    assert [event["id"] for event in events] == event_ids[::-1]
    limited = client.get("/users/me/events", headers=headers, params={"limit": 1})
    assert limited.status_code == 200 and len(limited.json()) == 1
    for limit in (0, 101, "invalid"):
        assert client.get("/users/me/events", headers=headers, params={"limit": limit}).status_code == 422
    for invalid in ({"event_type": " ", "item": "Dativ"},
                    {"event_type": "practice", "item": "Dativ", "user_id": "other"}):
        assert client.post("/users/me/events", headers=headers, json=invalid).status_code == 422
    assert client.get("/users/me/events", headers=other).json() == []
    session = client.post("/sessions", headers=headers).json()
    assert [row["id"] for row in client.get("/sessions", headers=headers).json()] == [session["id"]]
    assert client.get("/sessions", headers=other).json() == []
    route = f"/sessions/{session['id']}"
    uploaded = client.post(f"{route}/attachments", headers=headers,
                           files={"file": ("b2.txt", b"B2 public Dativ lesson", "text/plain")})
    assert uploaded.status_code == 200 and uploaded.json()["file_type"] == "txt"
    assert client.post(f"{route}/messages", headers=headers, json={"content": "Explain Dativ"}).status_code == 200
    assert len(client.get(f"{route}/messages", headers=headers).json()) == 2
    assert client.get(f"{route}/messages", headers=other).status_code == 404
    assert client.get("/sessions/missing-session/messages", headers=headers).status_code == 404
    return {"status": "PASS", "user_id": identity, "profile": profile,
            "event_ids": event_ids, "session_id": session["id"], "attachment_status": uploaded.status_code}


def verify_crm_persistence(client: httpx.Client, identity: str) -> dict:
    """Read a previous --crm identity after restarting the backend process."""
    headers = {"X-User-ID": identity}
    profile = client.get("/users/me/state", headers=headers)
    events = client.get("/users/me/events", headers=headers)
    sessions = client.get("/sessions", headers=headers)
    assert profile.status_code == events.status_code == sessions.status_code == 200
    expected = {"current_level": "A1", "target_level": "B1", "learning_goal": "Explain Dativ",
                "learning_preferences": "Simple examples"}
    assert all(profile.json()[key] == value for key, value in expected.items())
    assert [event["item"] for event in events.json()] == ["Dativ practice", "Dativ lesson"]
    return {"status": "PASS", "profile_status": profile.status_code,
            "event_count": len(events.json()), "session_count": len(sessions.json())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--crm", action="store_true", help="Also check B2 profile/events and attachments")
    parser.add_argument("--verify-crm-user", help="Verify profile/events after restarting the isolated backend")
    args = parser.parse_args()
    # Do not route loopback verification through any workstation HTTP proxy.
    with httpx.Client(base_url=args.base_url, timeout=5.0, trust_env=False) as client:
        health = client.get("/health")
        session = client.post("/sessions", headers=HEADERS)
        session.raise_for_status()
        session_id = session.json()["id"]
        normal = client.post(f"/sessions/{session_id}/messages", headers=HEADERS, json={"content": "Hello"})
        rag = client.post(f"/sessions/{session_id}/messages", headers=HEADERS, json={"content": "请解释德语 Dativ"})
        web = client.post(f"/sessions/{session_id}/messages", headers=HEADERS, json={"content": "今天柏林天气怎么样？"})
        messages = client.get(f"/sessions/{session_id}/messages", headers=HEADERS)
        crm_report = check_crm(client) if args.crm else None
        persistence_report = verify_crm_persistence(client, args.verify_crm_user) if args.verify_crm_user else None
    report = {
        "health_status": health.status_code,
        "health": {
            "router": health.json().get("router"),
            "router_configured_mode": health.json().get("router_configured_mode"),
            "router_initialized": health.json().get("router_initialized"),
            "web_search": health.json().get("web_search"),
            "web_provider_initialized": health.json().get("web_provider_initialized"),
            "tavily_api_key_configured": health.json().get("tavily_api_key_configured"),
            "tavily_connectivity": health.json().get("tavily_connectivity"),
        } if health.is_success else {},
        "session_status": session.status_code,
        "normal_status": normal.status_code,
        "rag_status": rag.status_code,
        "web_status": web.status_code,
        "message_status": messages.status_code,
        "message_roles": [item["role"] for item in messages.json()] if messages.is_success else [],
        "web_controlled_failure": "实时网页搜索失败" in web.json().get("assistant_message", {}).get("content", "") if web.is_success else False,
    }
    if crm_report is not None:
        report["crm"] = crm_report
    if persistence_report is not None:
        report["crm_persistence_after_restart"] = persistence_report
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    expected = all(report[key] == 200 for key in ("health_status", "session_status", "normal_status", "rag_status", "web_status", "message_status"))
    expected = expected and report["health"].get("router") in {"rules", "hybrid"}
    expected = expected and report["health"].get("router_configured_mode") == report["health"].get("router")
    expected = expected and report["health"].get("router_initialized") is True
    expected = expected and report["health"].get("web_provider_initialized") is True
    expected = expected and report["health"].get("tavily_api_key_configured") is False
    expected = expected and report["health"].get("tavily_connectivity") == "not_tested"
    return 0 if expected and report["message_roles"] == ["user", "assistant"] * 3 else 1


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
