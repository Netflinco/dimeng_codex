from __future__ import annotations

import base64
import json
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .storage import connect, encode, row_to_dict, rows_to_dicts

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
MAP_UPLOAD_DIR = WEB_ROOT / "uploads" / "floor-maps"
MAP_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
MAX_MAP_FILE_SIZE = 20 * 1024 * 1024
PROJECT_ADMIN_ROLES = {"project_admin", "system_admin"}
AUDIT_ROLES = {"project_admin", "system_admin", "security_supervisor"}
RULE_ACTIONS = {"create": "新增", "update": "编辑", "toggle": "启停", "copy": "复制", "delete": "删除"}
AI_WEBHOOK_APP_KEY = "demo-app-key"
AI_WEBHOOK_APP_SECRET = "demo-app-secret"
realtime_tokens = {}


def has_any_role(ctx, allowed):
    return bool(set(ctx.roles or []) & set(allowed))


def require_roles(ctx, allowed, code="forbidden", message="当前角色无权执行该操作"):
    if not has_any_role(ctx, allowed):
        raise ApiError(403, code, message)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit(conn, tenant_id, project_id, actor_id, action, object_type, object_id, result="success", detail=None):
    conn.execute(
        "INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (f"audit_{secrets.token_hex(8)}", tenant_id, project_id, actor_id, action, object_type, object_id, result, encode(detail or {}), now_text()),
    )


def login(tenant_code: str, username: str, password: str):
    with connect() as conn:
        tenant = conn.execute("SELECT * FROM tenants WHERE code = ?", (tenant_code,)).fetchone()
        user = None
        if tenant:
            user = conn.execute(
                "SELECT * FROM users WHERE tenantId = ? AND username = ? AND status = 'active'",
                (tenant["id"], username),
            ).fetchone()
        if not tenant or not user or user["password"] != password:
            if tenant:
                audit(conn, tenant["id"], None, None, "auth.login", "User", username, "failed", {"reason": "invalid_credentials"})
                conn.commit()
            raise ApiError(401, "invalid_credentials", "账号或密码错误")
        conn.execute("UPDATE users SET lastLoginAt = ? WHERE id = ?", (now_text(), user["id"]))
        audit(conn, tenant["id"], None, user["id"], "auth.login", "User", user["id"])
        conn.commit()
        return row_to_dict(user)


def projects_for_user(ctx):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.*, pm.roleIdsJson, pm.dataScope, pm.dataScopeIdsJson
            FROM projects p
            JOIN project_members pm ON pm.projectId = p.id
            WHERE pm.tenantId = ? AND pm.userId = ? AND pm.status = 'active'
            ORDER BY p.id
            """,
            (ctx.tenantId, ctx.userId),
        ).fetchall()
        pref = conn.execute("SELECT currentProjectId FROM user_preferences WHERE userId = ?", (ctx.userId,)).fetchone()
    return {
        "projects": rows_to_dicts(rows),
        "currentProjectId": pref["currentProjectId"] if pref else (rows[0]["id"] if rows else None),
    }


def set_current_project(ctx, project_id):
    with connect() as conn:
        if not conn.execute(
            "SELECT 1 FROM project_members WHERE tenantId = ? AND userId = ? AND projectId = ? AND status = 'active'",
            (ctx.tenantId, ctx.userId, project_id),
        ).fetchone():
            raise ApiError(403, "project_forbidden", "无权访问该项目")
        conn.execute(
            "INSERT INTO user_preferences(userId, currentProjectId) VALUES(?, ?) ON CONFLICT(userId) DO UPDATE SET currentProjectId = excluded.currentProjectId",
            (ctx.userId, project_id),
        )
        audit(conn, ctx.tenantId, project_id, ctx.userId, "project.switch", "Project", project_id)
        conn.commit()
    return {"currentProjectId": project_id}


def floors(project_id):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT f.*, fm.originalFileName, fm.displayImageUrl, fm.mimeType, fm.fileSize,
                   fm.status AS floorMapStatus, fm.uploadedAt
            FROM floors f
            LEFT JOIN floor_maps fm ON fm.id = f.floorMapId
            WHERE f.projectId = ?
            ORDER BY f.code
            """,
            (project_id,),
        ).fetchall()
        return rows_to_dicts(rows)


def floor_by_code_or_id(conn, project_id, floor):
    row = conn.execute("SELECT * FROM floors WHERE projectId = ? AND (id = ? OR code = ?)", (project_id, floor, floor)).fetchone()
    if not row:
        raise ApiError(404, "floor_not_found", "楼层不存在")
    return row


def nearest_area(point, labels):
    x = point["xRatio"]
    y = point["yRatio"]
    zone_by_x = 0 if x < 0.25 else 1 if x < 0.48 else 4 if x < 0.68 else 2
    zone_index = 3 if y > 0.54 else zone_by_x
    return labels[zone_index] if zone_index < len(labels) else "公共区"


def camera_rows(project_id, filters):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, d.deviceCode, d.deviceName, d.deviceType, d.deviceHealthStatus, d.edgeGatewayId,
                   p.id AS pointId, p.floorId, p.xRatio, p.yRatio, p.rotation,
                   f.code AS floorCode, f.labelsJson
            FROM cameras c
            JOIN devices d ON d.id = c.deviceId
            LEFT JOIN device_points p ON p.projectId = c.projectId AND p.deviceId = d.id
            LEFT JOIN floors f ON f.id = p.floorId
            WHERE c.projectId = ?
            ORDER BY d.deviceCode
            """,
            (project_id,),
        ).fetchall()
        items = []
        for row in rows:
            item = row_to_dict(row)
            if item.get("pointId"):
                labels = json.loads(row["labelsJson"])
                area = nearest_area({"xRatio": row["xRatio"], "yRatio": row["yRatio"]}, labels)
                item["location"] = {"floor": row["floorCode"], "area": area, "label": f"{row['floorCode']} / {area}"}
                item["pointConfigStatus"] = "configured"
            else:
                item["location"] = {"floor": "未配置", "area": "未配置", "label": "未配置"}
                item["pointConfigStatus"] = "unconfigured"
            if filters.get("floorId") and item["location"]["floor"] != filters["floorId"]:
                continue
            if filters.get("status") and item["deviceHealthStatus"] != filters["status"]:
                continue
            item.pop("streamAddressRef", None)
            items.append(item)
    return items


def project_summary(project_id):
    with connect() as conn:
        cameras_total = conn.execute("SELECT COUNT(*) FROM cameras WHERE projectId = ?", (project_id,)).fetchone()[0]
        online = conn.execute(
            "SELECT COUNT(*) FROM cameras c JOIN devices d ON d.id = c.deviceId WHERE c.projectId = ? AND d.deviceHealthStatus = 'online'",
            (project_id,),
        ).fetchone()[0]
        today_alarms = conn.execute("SELECT COUNT(*) FROM alarms WHERE projectId = ?", (project_id,)).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM alarms WHERE projectId = ? AND status NOT IN ('已关闭', '已标记误报')",
            (project_id,),
        ).fetchone()[0]
        project = row_to_dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
    return {
        "project": project,
        "cameraOnlineRate": round(online / cameras_total * 100) if cameras_total else 0,
        "todayAlarms": today_alarms,
        "pendingAlarms": pending,
        "aiEventsToday": 1248,
        "slaPassRate": 92,
    }


def points(project_id, floor_id):
    with connect() as conn:
        floor = floor_by_code_or_id(conn, project_id, floor_id)
        floor_map = conn.execute("SELECT * FROM floor_maps WHERE id = ?", (floor["floorMapId"],)).fetchone()
        rows = conn.execute(
            """
            SELECT p.*, d.deviceCode, d.deviceName, d.deviceHealthStatus, d.deviceType,
                   c.id AS cameraId, c.alarmState
            FROM device_points p
            JOIN devices d ON d.id = p.deviceId
            LEFT JOIN cameras c ON c.deviceId = d.id
            WHERE p.projectId = ? AND p.floorId = ?
            ORDER BY p.zIndex, p.id
            """,
            (project_id, floor["id"]),
        ).fetchall()
    floor_data = row_to_dict(floor)
    floor_data["map"] = row_to_dict(floor_map)
    return {"floor": floor_data, "points": rows_to_dicts(rows)}


def safe_file_name(name):
    stem = Path(name or "floor-map").stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._") or "floor-map"
    return stem[:80]


def parse_data_url(data_url):
    match = re.match(r"^data:([^;,]+);base64,(.+)$", data_url or "", re.S)
    if not match:
        raise ApiError(400, "invalid_data_url", "地图文件编码格式错误")
    mime_type = match.group(1)
    if mime_type not in MAP_MIME_TYPES:
        raise ApiError(400, "unsupported_map_type", "仅支持 PNG、JPG、WebP、SVG 楼层图")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except Exception:
        raise ApiError(400, "invalid_base64", "地图文件 Base64 内容错误")
    if len(raw) > MAX_MAP_FILE_SIZE:
        raise ApiError(400, "map_file_too_large", "地图文件不能超过 20MB")
    if mime_type == "image/svg+xml":
        svg = raw.decode("utf-8", errors="ignore")
        unsafe = re.search(r"<\s*script|foreignObject|on[a-z]+\s*=|href\s*=\s*['\"]https?:|xlink:href\s*=\s*['\"]https?:", svg, re.I)
        if unsafe:
            raise ApiError(400, "unsafe_svg", "SVG 包含脚本、事件属性或外链资源，已拒绝上传")
    return mime_type, raw


def upload_floor_map(ctx, project_id, floor_id, payload):
    file_name = payload.get("fileName") or "floor-map"
    data_url = payload.get("dataUrl")
    mime_type, raw = parse_data_url(data_url)
    with connect() as conn:
        floor = floor_by_code_or_id(conn, project_id, floor_id)
        next_version = int(floor["floorMapVersion"]) + 1
        next_map_id = f"map_{secrets.token_hex(8)}"
        extension = MAP_MIME_TYPES[mime_type]
        safe_name = safe_file_name(file_name)
        stored_name = f"{project_id}_{floor['code']}_v{next_version}_{safe_name}{extension}"
        MAP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        stored_path = MAP_UPLOAD_DIR / stored_name
        stored_path.write_bytes(raw)
        display_url = f"/uploads/floor-maps/{stored_name}"

        conn.execute(
            "UPDATE floor_maps SET status = 'archived' WHERE projectId = ? AND floorId = ? AND status = 'active'",
            (project_id, floor["id"]),
        )
        conn.execute(
            "INSERT INTO floor_maps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (next_map_id, ctx.tenantId, project_id, floor["id"], file_name, display_url, next_version, mime_type, len(raw), "active", None, ctx.userId, now_text()),
        )
        conn.execute(
            "UPDATE floors SET floorMapId = ?, floorMapVersion = ? WHERE id = ?",
            (next_map_id, next_version, floor["id"]),
        )
        audit(
            conn,
            ctx.tenantId,
            project_id,
            ctx.userId,
            "floorMap.upload",
            "FloorMap",
            next_map_id,
            detail={"floorId": floor["id"], "fileName": file_name, "mimeType": mime_type, "version": next_version},
        )
        conn.commit()
    return points(project_id, floor["id"])


def save_points(ctx, project_id, floor_id, payload):
    with connect() as conn:
        floor = floor_by_code_or_id(conn, project_id, floor_id)
        if int(payload.get("floorMapVersion", -1)) != floor["floorMapVersion"]:
            raise ApiError(409, "floor_map_version_conflict", "楼层图版本已变更，请刷新后重新校准")
        incoming = payload.get("points", [])
        seen = set()
        for point in incoming:
            device_id = point.get("deviceId")
            if not device_id or device_id in seen:
                raise ApiError(400, "duplicate_device_point", "同一设备不能重复配置点位")
            seen.add(device_id)
            if not (0 <= float(point.get("xRatio", -1)) <= 1 and 0 <= float(point.get("yRatio", -1)) <= 1):
                raise ApiError(400, "point_out_of_range", "点位坐标超出地图范围")
            device = conn.execute("SELECT * FROM devices WHERE projectId = ? AND id = ?", (project_id, device_id)).fetchone()
            if not device:
                raise ApiError(404, "device_not_found", f"设备不存在：{device_id}")
            existing_other = conn.execute(
                "SELECT * FROM device_points WHERE projectId = ? AND deviceId = ? AND floorId <> ?",
                (project_id, device_id, floor["id"]),
            ).fetchone()
            if existing_other:
                raise ApiError(409, "device_point_exists_on_other_floor", "该设备已配置在其他楼层")

        conn.execute("DELETE FROM device_points WHERE projectId = ? AND floorId = ?", (project_id, floor["id"]))
        for index, point in enumerate(incoming, start=1):
            device = conn.execute("SELECT * FROM devices WHERE id = ?", (point["deviceId"],)).fetchone()
            conn.execute(
                "INSERT INTO device_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"point_{secrets.token_hex(8)}",
                    ctx.tenantId,
                    project_id,
                    floor["id"],
                    floor["floorMapId"],
                    floor["floorMapVersion"],
                    point["deviceId"],
                    device["deviceType"],
                    float(point["xRatio"]),
                    float(point["yRatio"]),
                    int(point.get("rotation", 0)),
                    float(point.get("scale", 1)),
                    int(point.get("zIndex", index)),
                    point.get("iconType", "dome-camera"),
                    1 if point.get("visibleOnBigScreen", True) else 0,
                    int(point.get("version", 1)) + 1,
                ),
            )
        audit(conn, ctx.tenantId, project_id, ctx.userId, "map.points.save", "Floor", floor["id"], detail={"count": len(incoming)})
        conn.commit()
    return points(project_id, floor["id"])


def create_media_session(ctx, project_id, payload):
    camera_id = payload.get("cameraId")
    with connect() as conn:
        camera = conn.execute("SELECT * FROM cameras WHERE projectId = ? AND id = ?", (project_id, camera_id)).fetchone()
        if not camera:
            raise ApiError(404, "camera_not_found", "摄像头不存在")
        session_id = f"mps_{secrets.token_hex(8)}"
        expires = datetime.now() + timedelta(minutes=10)
        play_url = f"/mock-media/{session_id}.m3u8?token={secrets.token_urlsafe(12)}"
        failure = None if camera["mediaStatus"] == "playable" else camera["mediaStatus"]
        status = "created" if not failure else "failed"
        conn.execute(
            "INSERT INTO media_play_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, ctx.tenantId, project_id, camera_id, "WebRTC", play_url, expires.strftime("%Y-%m-%d %H:%M:%S"), status, failure, ctx.userId, now_text(), None),
        )
        audit(conn, ctx.tenantId, project_id, ctx.userId, "media.playSession.create", "Camera", camera_id, "failed" if failure else "success", {"failureReason": failure})
        conn.commit()
    return {"sessionId": session_id, "playUrl": play_url, "expiresAt": expires.isoformat(), "status": status, "failureReason": failure}


def release_media_session(ctx, session_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM media_play_sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            raise ApiError(404, "session_not_found", "播放会话不存在")
        conn.execute("UPDATE media_play_sessions SET status = 'released', releasedAt = ? WHERE id = ?", (now_text(), session_id))
        audit(conn, ctx.tenantId, row["projectId"], ctx.userId, "media.playSession.release", "MediaPlaySession", session_id)
        conn.commit()
    return {"released": True}


def alarm_list(project_id, status=None):
    sql = """
      SELECT a.*, d.deviceName, d.deviceCode, f.code AS floorCode
      FROM alarms a
      JOIN devices d ON d.id = a.deviceId
      LEFT JOIN floors f ON f.id = a.floorId
      WHERE a.projectId = ?
    """
    params = [project_id]
    if status and status != "all":
        sql += " AND a.status = ?"
        params.append(status)
    sql += " ORDER BY a.occurredAt DESC"
    with connect() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def alarm_detail(project_id, alarm_id):
    with connect() as conn:
        alarm = row_to_dict(conn.execute("SELECT * FROM alarms WHERE projectId = ? AND id = ?", (project_id, alarm_id)).fetchone())
        if not alarm:
            raise ApiError(404, "alarm_not_found", "告警不存在")
        actions = rows_to_dicts(conn.execute("SELECT * FROM alarm_actions WHERE alarmId = ? ORDER BY createdAt", (alarm_id,)).fetchall())
    alarm["actions"] = actions
    alarm["evidence"] = {"snapshotUrl": "/assets/evidence-placeholder.svg", "clipSeconds": 18, "retentionDays": 30}
    return alarm


TRANSITIONS = {
    "待确认": {"confirm": "已确认", "markFalsePositive": "已标记误报"},
    "已确认": {"assign": "已指派", "start": "处理中"},
    "已指派": {"assign": "已指派", "start": "处理中"},
    "处理中": {"assign": "处理中", "complete": "已完成"},
    "已完成": {"close": "已关闭"},
    "已标记误报": {"close": "已关闭"},
}


def alarm_action(ctx, project_id, alarm_id, payload, idempotency_key=None):
    action = payload.get("action")
    remark = payload.get("remark", "")
    with connect() as conn:
        alarm = conn.execute("SELECT * FROM alarms WHERE projectId = ? AND id = ?", (project_id, alarm_id)).fetchone()
        if not alarm:
            raise ApiError(404, "alarm_not_found", "告警不存在")
        if idempotency_key:
            existing = conn.execute(
                "SELECT * FROM alarm_actions WHERE alarmId = ? AND action = ? AND idempotencyKey = ?",
                (alarm_id, action, idempotency_key),
            ).fetchone()
            if existing:
                return alarm_detail(project_id, alarm_id)
        next_status = TRANSITIONS.get(alarm["status"], {}).get(action)
        if not next_status:
            raise ApiError(409, "invalid_alarm_transition", f"{alarm['status']} 不允许执行 {action}")
        if action == "markFalsePositive" and not remark.strip():
            raise ApiError(400, "false_positive_reason_required", "标记误报必须填写原因")
        assignee_user = payload.get("assigneeUserId")
        assignee_dept = payload.get("assigneeDeptId")
        updates = ["status = ?"]
        params = [next_status]
        if action == "assign":
            updates.extend(["assigneeUserId = ?", "assigneeDeptId = ?"])
            params.extend([assignee_user, assignee_dept])
        if action == "markFalsePositive":
            updates.append("falsePositiveReason = ?")
            params.append(remark)
        if action == "close":
            updates.append("closedAt = ?")
            params.append(now_text())
        params.append(alarm_id)
        conn.execute(f"UPDATE alarms SET {', '.join(updates)} WHERE id = ?", params)
        conn.execute(
            "INSERT INTO alarm_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"act_{secrets.token_hex(8)}", ctx.tenantId, project_id, alarm_id, action, ctx.userId, assignee_user, assignee_dept, remark, idempotency_key, now_text()),
        )
        audit(conn, ctx.tenantId, project_id, ctx.userId, f"alarm.{action}", "Alarm", alarm_id, detail={"from": alarm["status"], "to": next_status})
        conn.commit()
    return alarm_detail(project_id, alarm_id)


def rules(project_id):
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM inspection_rules WHERE projectId = ? ORDER BY id", (project_id,)).fetchall())


def rule_by_id(conn, project_id, rule_id):
    row = conn.execute("SELECT * FROM inspection_rules WHERE projectId = ? AND id = ?", (project_id, rule_id)).fetchone()
    if not row:
        raise ApiError(404, "rule_not_found", "规则不存在")
    return row


def normalize_rule_payload(payload, fallback=None):
    fallback = fallback or {}
    target_ids = payload.get("targetIds", fallback.get("targetIdsJson", ["mall_001"]))
    exclude_ids = payload.get("excludeDeviceIds", fallback.get("excludeDeviceIdsJson", []))
    return {
        "name": payload.get("name", fallback.get("name", "新规则")),
        "ruleType": payload.get("ruleType", fallback.get("ruleType", "人员聚集")),
        "eventType": payload.get("eventType", fallback.get("eventType", "crowd")),
        "targetScope": payload.get("targetScope", fallback.get("targetScope", "project")),
        "targetIds": target_ids if isinstance(target_ids, list) else [target_ids],
        "excludeDeviceIds": exclude_ids if isinstance(exclude_ids, list) else [exclude_ids],
        "threshold": float(payload.get("threshold", fallback.get("threshold", 0.85))),
        "cooldownSeconds": int(payload.get("cooldownSeconds", fallback.get("cooldownSeconds", 300))),
        "sourceProvider": payload.get("sourceProvider", fallback.get("sourceProvider", "MegviiBox")),
        "modelName": payload.get("modelName", fallback.get("modelName", "ThirdPartyModel")),
        "modelVersion": payload.get("modelVersion", fallback.get("modelVersion", "1.0.0")),
        "enabled": 1 if payload.get("enabled", fallback.get("enabled", True)) else 0,
    }


def create_rule(ctx, project_id, payload):
    data = normalize_rule_payload(payload)
    rule_id = f"rule_{secrets.token_hex(6)}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO inspection_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                rule_id,
                ctx.tenantId,
                project_id,
                data["name"],
                data["ruleType"],
                data["eventType"],
                data["targetScope"],
                encode(data["targetIds"]),
                encode(data["excludeDeviceIds"]),
                data["threshold"],
                data["cooldownSeconds"],
                data["sourceProvider"],
                data["modelName"],
                data["modelVersion"],
                data["enabled"],
                0,
                0,
                0,
            ),
        )
        audit(conn, ctx.tenantId, project_id, ctx.userId, "rule.create", "InspectionRule", rule_id, detail={"name": data["name"]})
        conn.commit()
        return row_to_dict(rule_by_id(conn, project_id, rule_id))


def update_rule(ctx, project_id, rule_id, payload):
    with connect() as conn:
        current = row_to_dict(rule_by_id(conn, project_id, rule_id))
        data = normalize_rule_payload(payload, current)
        conn.execute(
            """
            UPDATE inspection_rules
            SET name = ?, ruleType = ?, eventType = ?, targetScope = ?, targetIdsJson = ?,
                excludeDeviceIdsJson = ?, threshold = ?, cooldownSeconds = ?, sourceProvider = ?,
                modelName = ?, modelVersion = ?, enabled = ?
            WHERE id = ?
            """,
            (
                data["name"],
                data["ruleType"],
                data["eventType"],
                data["targetScope"],
                encode(data["targetIds"]),
                encode(data["excludeDeviceIds"]),
                data["threshold"],
                data["cooldownSeconds"],
                data["sourceProvider"],
                data["modelName"],
                data["modelVersion"],
                data["enabled"],
                rule_id,
            ),
        )
        audit(conn, ctx.tenantId, project_id, ctx.userId, "rule.update", "InspectionRule", rule_id)
        conn.commit()
        return row_to_dict(rule_by_id(conn, project_id, rule_id))


def toggle_rule(ctx, project_id, rule_id, enabled):
    with connect() as conn:
        rule_by_id(conn, project_id, rule_id)
        conn.execute("UPDATE inspection_rules SET enabled = ? WHERE id = ?", (1 if enabled else 0, rule_id))
        audit(conn, ctx.tenantId, project_id, ctx.userId, "rule.toggle", "InspectionRule", rule_id, detail={"enabled": bool(enabled)})
        conn.commit()
        return row_to_dict(rule_by_id(conn, project_id, rule_id))


def copy_rule(ctx, project_id, rule_id):
    with connect() as conn:
        current = row_to_dict(rule_by_id(conn, project_id, rule_id))
    current["name"] = f"{current['name']} 副本"
    return create_rule(ctx, project_id, current)


def delete_rule(ctx, project_id, rule_id):
    with connect() as conn:
        rule_by_id(conn, project_id, rule_id)
        conn.execute("DELETE FROM inspection_rules WHERE id = ?", (rule_id,))
        audit(conn, ctx.tenantId, project_id, ctx.userId, "rule.delete", "InspectionRule", rule_id)
        conn.commit()
    return {"deleted": True}


def find_matching_rule(conn, project_id, event_type, source_provider, device_id, camera_id, floor_id, confidence):
    rows = conn.execute(
        """
        SELECT * FROM inspection_rules
        WHERE projectId = ? AND sourceProvider = ? AND eventType = ? AND enabled = 1
        ORDER BY threshold DESC
        """,
        (project_id, source_provider, event_type),
    ).fetchall()
    for row in rows:
        rule = row_to_dict(row)
        if device_id in (rule.get("excludeDeviceIdsJson") or []):
            continue
        if confidence < float(rule["threshold"]):
            continue
        target_ids = rule.get("targetIdsJson") or []
        scope = rule["targetScope"]
        matched = (
            scope == "project" and (not target_ids or project_id in target_ids)
            or scope == "device" and device_id in target_ids
            or scope == "camera" and camera_id in target_ids
            or scope == "floor" and floor_id in target_ids
        )
        if matched:
            return rule
    return None


def ingest_ai_event(payload):
    tenant_id = payload.get("tenantId", "tenant_001")
    project_id = payload.get("projectId")
    source_provider = payload.get("sourceProvider", "MegviiBox")
    source_event_id = payload.get("sourceEventId")
    source_code = payload.get("cameraCode") or payload.get("deviceCode")
    event_type = payload.get("eventType")
    confidence = float(payload.get("confidence", 0))
    occurred_at = payload.get("occurredAt") or now_text()
    if not project_id or not source_event_id or not source_code or not event_type:
        raise ApiError(400, "invalid_source_event", "缺少 projectId/sourceEventId/cameraCode/eventType")
    idempotency_key = f"{tenant_id}:{project_id}:{source_provider}:{source_event_id}"
    with connect() as conn:
        exists = conn.execute("SELECT * FROM source_events WHERE idempotencyKey = ?", (idempotency_key,)).fetchone()
        if exists:
            return {"accepted": True, "sourceEventId": exists["id"], "status": exists["status"], "idempotent": True}

        device_row = conn.execute(
            """
            SELECT d.*, c.id AS cameraId, p.floorId, p.xRatio, p.yRatio, f.labelsJson
            FROM devices d
            LEFT JOIN cameras c ON c.deviceId = d.id
            LEFT JOIN device_points p ON p.deviceId = d.id AND p.projectId = d.projectId
            LEFT JOIN floors f ON f.id = p.floorId
            WHERE d.projectId = ? AND d.deviceCode = ? AND d.enabled = 1
            """,
            (project_id, source_code),
        ).fetchone()
        source_id = f"src_{secrets.token_hex(8)}"
        if not device_row:
            conn.execute(
                "INSERT INTO source_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (source_id, tenant_id, project_id, source_provider, source_event_id, idempotency_key, source_code, None, None, event_type, confidence, occurred_at, payload.get("modelName"), payload.get("modelVersion"), encode(payload), "failed", "device_mapping_not_found", "设备编码未映射"),
            )
            conn.commit()
            return {"accepted": True, "sourceEventId": source_id, "status": "failed"}

        rule = find_matching_rule(
            conn,
            project_id,
            event_type,
            source_provider,
            device_row["id"],
            device_row["cameraId"],
            device_row["floorId"],
            confidence,
        )
        source_status = "discarded" if not rule else "normalized"
        conn.execute(
            "INSERT INTO source_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                tenant_id,
                project_id,
                source_provider,
                source_event_id,
                idempotency_key,
                source_code,
                device_row["cameraId"],
                device_row["id"],
                event_type,
                confidence,
                occurred_at,
                payload.get("modelName"),
                payload.get("modelVersion"),
                encode(payload),
                source_status,
                None if rule else "no_matching_rule_or_low_confidence",
                None if rule else "无匹配规则或低于阈值",
            ),
        )
        if not rule:
            conn.commit()
            return {"accepted": True, "sourceEventId": source_id, "status": "discarded"}

        dedupe_key = f"{rule['id']}:{device_row['id']}:{event_type}"
        open_alarm = conn.execute(
            "SELECT id FROM alarms WHERE projectId = ? AND dedupeKey = ? AND status NOT IN ('已关闭', '已标记误报')",
            (project_id, dedupe_key),
        ).fetchone()
        if open_alarm:
            conn.execute("UPDATE source_events SET status = ?, errorCode = ?, errorMessage = ? WHERE id = ?", ("filtered", "cooldown_dedupe", "冷却期内已有有效告警", source_id))
            conn.commit()
            return {"accepted": True, "sourceEventId": source_id, "status": "filtered", "alarmId": open_alarm["id"]}

        labels = json.loads(device_row["labelsJson"]) if device_row["labelsJson"] else []
        area = nearest_area({"xRatio": device_row["xRatio"] or 0.5, "yRatio": device_row["yRatio"] or 0.5}, labels) if labels else "未配置"
        alarm_id = f"alm_{secrets.token_hex(6)}"
        level = "P1" if confidence >= 0.93 else "P2" if confidence >= 0.86 else "P3"
        deadline = (datetime.now() + timedelta(minutes=30 if level != "P1" else 10)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO alarms VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                alarm_id,
                tenant_id,
                project_id,
                rule["ruleType"],
                level,
                "待确认",
                dedupe_key,
                source_provider,
                source_event_id,
                device_row["cameraId"],
                device_row["id"],
                device_row["floorId"],
                area,
                payload.get("modelName", rule["modelName"]),
                payload.get("modelVersion", rule["modelVersion"]),
                confidence,
                int(confidence * 100),
                f"evd_{alarm_id}",
                occurred_at,
                deadline,
                "normal",
                None,
                None,
                None,
                None,
            ),
        )
        conn.execute(
            "INSERT INTO alarm_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"act_{secrets.token_hex(8)}", tenant_id, project_id, alarm_id, "created", "system", None, None, "AI 事件自动生成告警", None, now_text()),
        )
        conn.execute("UPDATE source_events SET status = ? WHERE id = ?", ("alarmGenerated", source_id))
        conn.execute("UPDATE inspection_rules SET hitCount = hitCount + 1, alarmCount = alarmCount + 1 WHERE id = ?", (rule["id"],))
        audit(conn, tenant_id, project_id, "system", "alarm.created", "Alarm", alarm_id, detail={"sourceEventId": source_id})
        conn.commit()
    return {"accepted": True, "sourceEventId": source_id, "status": "alarmGenerated", "alarmId": alarm_id}


def create_realtime_token(ctx, project_id):
    token = secrets.token_urlsafe(24)
    expires_at = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    realtime_tokens[token] = {"projectId": project_id, "userId": ctx.userId, "expiresAt": datetime.now() + timedelta(minutes=15)}
    return {"token": token, "projectId": project_id, "expiresAt": expires_at, "eventsUrl": f"/api/projects/{project_id}/realtime/events?token={token}"}


def validate_realtime_token(project_id, token):
    item = realtime_tokens.get(token)
    return bool(item and item["projectId"] == project_id and item["expiresAt"] > datetime.now())


def create_evidence_download_token(ctx, project_id, evidence_id):
    with connect() as conn:
        alarm = conn.execute("SELECT id FROM alarms WHERE projectId = ? AND evidenceId = ?", (project_id, evidence_id)).fetchone()
        if not alarm:
            raise ApiError(404, "evidence_not_found", "证据不存在")
        token = secrets.token_urlsafe(24)
        expires_at = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        audit(conn, ctx.tenantId, project_id, ctx.userId, "evidence.downloadToken.create", "Evidence", evidence_id, detail={"alarmId": alarm["id"]})
        conn.commit()
    return {"downloadToken": token, "expiresAt": expires_at, "downloadUrl": f"/api/evidence/downloads/{token}"}


def delete_evidence(ctx, project_id, evidence_id):
    with connect() as conn:
        alarm = conn.execute("SELECT id FROM alarms WHERE projectId = ? AND evidenceId = ?", (project_id, evidence_id)).fetchone()
        if not alarm:
            raise ApiError(404, "evidence_not_found", "证据不存在")
        audit(conn, ctx.tenantId, project_id, ctx.userId, "evidence.softDelete", "Evidence", evidence_id, detail={"alarmId": alarm["id"], "fileHashRetained": True})
        conn.commit()
    return {"deleted": True, "softDeleted": True, "evidenceId": evidence_id}


def add_alarm_attachment(ctx, project_id, alarm_id, payload, idempotency_key=None):
    file_name = payload.get("fileName")
    mime_type = payload.get("mimeType", "")
    file_size = int(payload.get("fileSize", 0))
    if not file_name:
        raise ApiError(400, "attachment_name_required", "附件文件名不能为空")
    if file_size > 20 * 1024 * 1024:
        raise ApiError(400, "attachment_too_large", "附件不能超过 20MB")
    if mime_type and not (mime_type.startswith("image/") or mime_type in {"application/pdf", "text/plain"}):
        raise ApiError(400, "attachment_type_unsupported", "仅支持图片、PDF 或文本附件")
    with connect() as conn:
        alarm = conn.execute("SELECT * FROM alarms WHERE projectId = ? AND id = ?", (project_id, alarm_id)).fetchone()
        if not alarm:
            raise ApiError(404, "alarm_not_found", "告警不存在")
        if idempotency_key:
            existing = conn.execute(
                "SELECT * FROM alarm_actions WHERE alarmId = ? AND action = ? AND idempotencyKey = ?",
                (alarm_id, "attach", idempotency_key),
            ).fetchone()
            if existing:
                return {"attached": True, "idempotent": True, "attachmentId": existing["id"]}
        attachment_id = f"att_{secrets.token_hex(8)}"
        remark = f"上传附件：{file_name}"
        conn.execute(
            "INSERT INTO alarm_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (attachment_id, ctx.tenantId, project_id, alarm_id, "attach", ctx.userId, None, None, remark, idempotency_key, now_text()),
        )
        audit(conn, ctx.tenantId, project_id, ctx.userId, "alarm.attachment.upload", "Alarm", alarm_id, detail={"fileName": file_name, "mimeType": mime_type, "fileSize": file_size})
        conn.commit()
    return {"attached": True, "attachmentId": attachment_id}


def create_alarm_export(ctx, project_id, payload):
    export_id = f"exp_{secrets.token_hex(8)}"
    with connect() as conn:
        audit(conn, ctx.tenantId, project_id, ctx.userId, "alarm.export.create", "ExportTask", export_id, detail={"filters": payload or {}})
        conn.commit()
    return {
        "exportTaskId": export_id,
        "status": "completed",
        "downloadUrl": f"/api/projects/{project_id}/exports/{export_id}/download",
        "expiresAt": (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
    }


def audit_logs(project_id):
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM audit_logs WHERE projectId = ? OR projectId IS NULL ORDER BY createdAt DESC LIMIT 50", (project_id,)).fetchall())
