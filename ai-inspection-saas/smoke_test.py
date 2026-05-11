from __future__ import annotations

import json
import base64
import hashlib
import hmac
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8090"
AI_APP_KEY = "demo-app-key"
AI_APP_SECRET = "demo-app-secret"


def request(method, path, token=None, body=None, headers=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as err:
        payload = json.loads(err.read().decode("utf-8") or "{}")
        return err.code, payload


def request_text(method, path, token=None, body=None, headers=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


def signed_ai_event(payload, nonce="smoke-nonce-001"):
    raw = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    body_hash = hashlib.sha256(raw).hexdigest()
    canonical = "\n".join(["POST", "/ai-events/source-events", timestamp, nonce, body_hash])
    signature = hmac.new(AI_APP_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        BASE + "/ai-events/source-events",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-App-Key": AI_APP_KEY,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8") or "{}")


def main():
    status, login = request("POST", "/api/auth/login", body={"tenantCode": "joycity-demo", "username": "operator01", "password": "123456"})
    assert status == 200, login
    operator_token = login["token"]
    project_id = login["currentProjectId"]

    status, projects = request("GET", "/api/me/projects", operator_token)
    assert status == 200 and projects["projects"], projects

    status, forbidden = request("GET", f"/api/projects/{project_id}/audit-logs", operator_token)
    assert status == 403 and forbidden["code"] == "audit_forbidden", forbidden

    status, forbidden = request("PUT", f"/api/projects/{project_id}/points/floors/L1", operator_token, body={"floorMapVersion": 3, "points": []})
    assert status == 403 and forbidden["code"] == "map_config_forbidden", forbidden

    status, admin_login = request("POST", "/api/auth/login", body={"tenantCode": "joycity-demo", "username": "admin", "password": "123456"})
    assert status == 200, admin_login
    token = admin_login["token"]

    status, cameras = request("GET", f"/api/projects/{project_id}/cameras", token)
    assert status == 200 and cameras["cameras"], cameras
    assert "streamAddressRef" not in json.dumps(cameras), cameras

    status, points = request("GET", f"/api/projects/{project_id}/points?floorId=L1", token)
    assert status == 200 and points["points"], points
    current_map_version = points["floor"]["floorMapVersion"]
    saved_points = [
        {"deviceId": item["deviceId"], "xRatio": item["xRatio"], "yRatio": item["yRatio"], "rotation": item["rotation"], "version": item["version"]}
        for item in points["points"]
    ]
    saved_points[0]["xRatio"] = 0.36
    status, saved = request("PUT", f"/api/projects/{project_id}/points/floors/L1", token, body={"floorMapVersion": current_map_version, "points": saved_points})
    assert status == 200 and saved["points"][0]["xRatio"] == 0.36, saved

    svg = "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='240'><rect width='400' height='240' fill='#eef6fb'/><path d='M40 60h300v120H40z' fill='none' stroke='#0f8b8d'/></svg>"
    data_url = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    status, uploaded = request(
        "POST",
        f"/api/projects/{project_id}/floors/L1/map",
        token,
        body={"fileName": "smoke-map.svg", "mimeType": "image/svg+xml", "dataUrl": data_url},
    )
    assert status == 201 and uploaded["floor"]["floorMapVersion"] == current_map_version + 1 and uploaded["floor"]["map"]["displayImageUrl"], uploaded
    status, conflict = request("PUT", f"/api/projects/{project_id}/points/floors/L1", token, body={"floorMapVersion": current_map_version, "points": saved_points})
    assert status == 409 and conflict["code"] == "floor_map_version_conflict", conflict

    status, empty_points = request("GET", "/api/projects/mall_002/points?floorId=L1", token)
    assert status == 200 and empty_points["points"] == [], empty_points

    status, rule = request(
        "POST",
        f"/api/projects/{project_id}/rules",
        token,
        body={"name": "冒烟规则", "ruleType": "人员聚集", "eventType": "crowd", "sourceProvider": "MegviiBox", "threshold": 0.86, "targetScope": "project", "targetIds": [project_id]},
    )
    assert status == 201 and rule["name"] == "冒烟规则", rule
    status, toggled = request("POST", f"/api/projects/{project_id}/rules/{rule['id']}/toggle", token, body={"enabled": False})
    assert status == 200 and toggled["enabled"] == 0, toggled
    status, copied = request("POST", f"/api/projects/{project_id}/rules/{rule['id']}/copy", token, body={})
    assert status == 201 and copied["id"] != rule["id"], copied
    status, deleted = request("DELETE", f"/api/projects/{project_id}/rules/{copied['id']}", token)
    assert status == 200 and deleted["deleted"], deleted

    status, ai_result = signed_ai_event(
        {
            "tenantId": "tenant_001",
            "projectId": project_id,
            "sourceProvider": "MegviiBox",
            "sourceEventId": "smoke-ai-001",
            "cameraCode": "CAM-L1-004",
            "eventType": "crowd",
            "confidence": 0.92,
            "occurredAt": "2026-05-11 11:00:00",
            "modelName": "CrowdSense",
            "modelVersion": "2.1.0",
        }
    )
    assert status == 202 and ai_result["status"] == "alarmGenerated" and ai_result["alarmId"], ai_result
    status, replay = signed_ai_event(
        {
            "tenantId": "tenant_001",
            "projectId": project_id,
            "sourceProvider": "MegviiBox",
            "sourceEventId": "smoke-ai-001",
            "cameraCode": "CAM-L1-004",
            "eventType": "crowd",
            "confidence": 0.92,
        }
    )
    assert status == 401 and replay["code"] == "nonce_replay", replay
    status, duplicate = signed_ai_event(
        {
            "tenantId": "tenant_001",
            "projectId": project_id,
            "sourceProvider": "MegviiBox",
            "sourceEventId": "smoke-ai-001",
            "cameraCode": "CAM-L1-004",
            "eventType": "crowd",
            "confidence": 0.92,
        },
        nonce="smoke-nonce-001b",
    )
    assert status == 202 and duplicate["idempotent"], duplicate

    status, bad_ai = signed_ai_event(
        {
            "tenantId": "tenant_001",
            "projectId": project_id,
            "sourceProvider": "MegviiBox",
            "sourceEventId": "smoke-ai-002",
            "cameraCode": "UNKNOWN",
            "eventType": "crowd",
            "confidence": 0.92,
        },
        nonce="smoke-nonce-002",
    )
    assert status == 202 and bad_ai["status"] == "failed", bad_ai

    status, rt = request("POST", f"/api/projects/{project_id}/realtime/token", token, body={})
    assert status == 201 and rt["projectId"] == project_id and rt["token"], rt
    status, sse = request_text("GET", rt["eventsUrl"], token)
    assert status == 200 and "connected" in sse, sse

    status, session = request("POST", f"/api/projects/{project_id}/media/play-sessions", token, body={"cameraId": cameras["cameras"][0]["id"]})
    assert status == 201 and "playUrl" in session and "secret://" not in session["playUrl"], session
    request("DELETE", f"/api/media/play-sessions/{session['sessionId']}", token)

    status, alarms = request("GET", f"/api/projects/{project_id}/alarms", token)
    assert status == 200 and alarms["alarms"], alarms
    status, evd = request("POST", f"/api/projects/{project_id}/evidence/{alarms['alarms'][0]['evidenceId']}/download-token", token, body={})
    assert status == 201 and evd["downloadToken"], evd
    status, attachment = request(
        "POST",
        f"/api/projects/{project_id}/alarms/{alarms['alarms'][0]['id']}/attachments",
        token,
        body={"fileName": "现场照片.jpg", "mimeType": "image/jpeg", "fileSize": 2048},
        headers={"Idempotency-Key": "smoke-attachment-001"},
    )
    assert status == 201 and attachment["attached"], attachment
    status, export_task = request("POST", f"/api/projects/{project_id}/exports/alarms", token, body={"status": "all"})
    assert status == 201 and export_task["status"] == "completed" and export_task["downloadUrl"], export_task
    status, evidence_deleted = request("DELETE", f"/api/projects/{project_id}/evidence/{alarms['alarms'][0]['evidenceId']}", token)
    assert status == 200 and evidence_deleted["softDeleted"], evidence_deleted
    pending = next(item for item in alarms["alarms"] if item["status"] == "待确认")
    status, alarm = request(
        "POST",
        f"/api/projects/{project_id}/alarms/{pending['id']}/actions",
        token,
        body={"action": "confirm", "remark": "冒烟测试确认有效"},
        headers={"Idempotency-Key": "smoke-confirm-001"},
    )
    assert status == 200 and alarm["status"] == "已确认", alarm

    status, bad = request("GET", "/api/projects/mall_002/cameras", operator_token)
    assert status == 403, bad

    print("smoke ok: permissions, project isolation, empty project, cameras, points, floor map upload, rules, AI event, realtime token, evidence token, attachments, export, media session, alarm state machine")


if __name__ == "__main__":
    main()
