from __future__ import annotations

import json
import mimetypes
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app import services
from app.security import create_session, get_context, require_project, verify_webhook_signature
from app.storage import init_db

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"


class Handler(BaseHTTPRequestHandler):
    server_version = "AIInspectionMVP/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status=200, body=None, headers=None):
        payload = b""
        headers = headers or {}
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, Idempotency-Key, X-App-Key, X-Timestamp, X-Nonce, X-Signature")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def _error(self, err):
        if isinstance(err, services.ApiError):
            self._send(err.status, {"code": err.code, "message": err.message, **err.extra})
        else:
            self._send(500, {"code": "internal_error", "message": str(err)})

    def _json_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _raw_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b"{}"

    def _ctx(self):
        ctx = get_context(self.headers)
        if not ctx:
            raise services.ApiError(401, "unauthorized", "请先登录")
        return ctx

    def _require_project(self, project_id):
        ctx = self._ctx()
        member = require_project(ctx, project_id)
        if not member:
            raise services.ApiError(403, "project_forbidden", "无权访问该项目")
        return ctx

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}

            if path.startswith("/api/"):
                return self.route_get(path, qs)
            return self.serve_static(path)
        except Exception as err:
            self._error(err)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/ai-events/source-events":
                raw = self._raw_body()
                return self.route_ai_event(parsed.path, raw)
            body = self._json_body()
            self.route_write("POST", parsed.path, body)
        except Exception as err:
            self._error(err)

    def do_PUT(self):
        try:
            parsed = urlparse(self.path)
            body = self._json_body()
            self.route_write("PUT", parsed.path, body)
        except Exception as err:
            self._error(err)

    def do_DELETE(self):
        try:
            parsed = urlparse(self.path)
            self.route_write("DELETE", parsed.path, {})
        except Exception as err:
            self._error(err)

    def route_get(self, path, qs):
        if path == "/api/me/projects":
            return self._send(200, services.projects_for_user(self._ctx()))

        match = re.fullmatch(r"/api/projects/([^/]+)/summary", path)
        if match:
            project_id = match.group(1)
            self._require_project(project_id)
            return self._send(200, services.project_summary(project_id))

        match = re.fullmatch(r"/api/projects/([^/]+)/floors", path)
        if match:
            project_id = match.group(1)
            self._require_project(project_id)
            return self._send(200, {"floors": services.floors(project_id)})

        match = re.fullmatch(r"/api/projects/([^/]+)/cameras", path)
        if match:
            project_id = match.group(1)
            self._require_project(project_id)
            return self._send(200, {"cameras": services.camera_rows(project_id, qs)})

        match = re.fullmatch(r"/api/projects/([^/]+)/points", path)
        if match:
            project_id = match.group(1)
            self._require_project(project_id)
            return self._send(200, services.points(project_id, qs.get("floorId", "L1")))

        match = re.fullmatch(r"/api/projects/([^/]+)/alarms", path)
        if match:
            project_id = match.group(1)
            self._require_project(project_id)
            return self._send(200, {"alarms": services.alarm_list(project_id, qs.get("status"))})

        match = re.fullmatch(r"/api/projects/([^/]+)/alarms/([^/]+)", path)
        if match:
            project_id, alarm_id = match.groups()
            self._require_project(project_id)
            return self._send(200, services.alarm_detail(project_id, alarm_id))

        match = re.fullmatch(r"/api/projects/([^/]+)/rules", path)
        if match:
            project_id = match.group(1)
            self._require_project(project_id)
            return self._send(200, {"rules": services.rules(project_id)})

        match = re.fullmatch(r"/api/projects/([^/]+)/audit-logs", path)
        if match:
            project_id = match.group(1)
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.AUDIT_ROLES, "audit_forbidden", "无权查看审计日志")
            return self._send(200, {"auditLogs": services.audit_logs(project_id)})

        match = re.fullmatch(r"/api/projects/([^/]+)/realtime/events", path)
        if match:
            project_id = match.group(1)
            token = qs.get("token")
            if not services.validate_realtime_token(project_id, token):
                raise services.ApiError(401, "realtime_token_invalid", "实时订阅 token 无效或已过期")
            return self._send_sse(project_id)

        raise services.ApiError(404, "not_found", "接口不存在")

    def _send_sse(self, project_id):
        payload = json.dumps({"type": "connected", "projectId": project_id}, ensure_ascii=False)
        body = f"event: connected\ndata: {payload}\n\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def route_ai_event(self, path, raw):
        if self.headers.get("X-App-Key") != services.AI_WEBHOOK_APP_KEY:
            raise services.ApiError(401, "bad_app_key", "AI 接入 appKey 无效")
        ok, reason = verify_webhook_signature("POST", path, raw, self.headers, services.AI_WEBHOOK_APP_SECRET)
        if not ok:
            raise services.ApiError(401, reason or "bad_signature", "AI 事件签名校验失败")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise services.ApiError(400, "invalid_json", "AI 事件 JSON 格式错误")
        result = services.ingest_ai_event(payload)
        return self._send(202, result)

    def route_write(self, method, path, body):
        if method == "POST" and path == "/api/auth/login":
            user = services.login(body.get("tenantCode", ""), body.get("username", ""), body.get("password", ""))
            token = create_session(user)
            ctx = get_context({"Authorization": f"Bearer {token}"})
            projects = services.projects_for_user(ctx)
            return self._send(200, {
                "token": token,
                "user": {
                    "id": user["id"],
                    "name": user["name"],
                    "username": user["username"],
                    "roles": user["rolesJson"],
                    "projectIds": [p["id"] for p in projects["projects"]],
                },
                **projects,
            })

        if method == "POST" and path == "/api/me/preferences/current-project":
            ctx = self._ctx()
            return self._send(200, services.set_current_project(ctx, body.get("projectId")))

        match = re.fullmatch(r"/api/projects/([^/]+)/points/floors/([^/]+)", path)
        if method == "PUT" and match:
            project_id, floor_id = match.groups()
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "map_config_forbidden", "无权保存点位配置")
            return self._send(200, services.save_points(ctx, project_id, floor_id, body))

        match = re.fullmatch(r"/api/projects/([^/]+)/floors/([^/]+)/map", path)
        if method == "POST" and match:
            project_id, floor_id = match.groups()
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "map_upload_forbidden", "无权维护楼层地图")
            return self._send(201, services.upload_floor_map(ctx, project_id, floor_id, body))

        match = re.fullmatch(r"/api/projects/([^/]+)/rules", path)
        if method == "POST" and match:
            project_id = match.group(1)
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "rule_forbidden", "无权维护规则")
            return self._send(201, services.create_rule(ctx, project_id, body))

        match = re.fullmatch(r"/api/projects/([^/]+)/rules/([^/]+)", path)
        if match and method in {"PUT", "DELETE"}:
            project_id, rule_id = match.groups()
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "rule_forbidden", "无权维护规则")
            if method == "PUT":
                return self._send(200, services.update_rule(ctx, project_id, rule_id, body))
            return self._send(200, services.delete_rule(ctx, project_id, rule_id))

        match = re.fullmatch(r"/api/projects/([^/]+)/rules/([^/]+)/toggle", path)
        if method == "POST" and match:
            project_id, rule_id = match.groups()
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "rule_forbidden", "无权维护规则")
            return self._send(200, services.toggle_rule(ctx, project_id, rule_id, bool(body.get("enabled"))))

        match = re.fullmatch(r"/api/projects/([^/]+)/rules/([^/]+)/copy", path)
        if method == "POST" and match:
            project_id, rule_id = match.groups()
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "rule_forbidden", "无权维护规则")
            return self._send(201, services.copy_rule(ctx, project_id, rule_id))

        match = re.fullmatch(r"/api/projects/([^/]+)/realtime/token", path)
        if method == "POST" and match:
            project_id = match.group(1)
            ctx = self._require_project(project_id)
            return self._send(201, services.create_realtime_token(ctx, project_id))

        match = re.fullmatch(r"/api/projects/([^/]+)/evidence/([^/]+)/download-token", path)
        if method == "POST" and match:
            project_id, evidence_id = match.groups()
            ctx = self._require_project(project_id)
            return self._send(201, services.create_evidence_download_token(ctx, project_id, evidence_id))

        match = re.fullmatch(r"/api/projects/([^/]+)/media/play-sessions", path)
        if method == "POST" and match:
            project_id = match.group(1)
            ctx = self._require_project(project_id)
            return self._send(201, services.create_media_session(ctx, project_id, body))

        match = re.fullmatch(r"/api/media/play-sessions/([^/]+)", path)
        if method == "DELETE" and match:
            ctx = self._ctx()
            return self._send(200, services.release_media_session(ctx, match.group(1)))

        match = re.fullmatch(r"/api/projects/([^/]+)/alarms/([^/]+)/actions", path)
        if method == "POST" and match:
            project_id, alarm_id = match.groups()
            ctx = self._require_project(project_id)
            idem = self.headers.get("Idempotency-Key")
            return self._send(200, services.alarm_action(ctx, project_id, alarm_id, body, idem))

        match = re.fullmatch(r"/api/projects/([^/]+)/alarms/([^/]+)/attachments", path)
        if method == "POST" and match:
            project_id, alarm_id = match.groups()
            ctx = self._require_project(project_id)
            idem = self.headers.get("Idempotency-Key")
            return self._send(201, services.add_alarm_attachment(ctx, project_id, alarm_id, body, idem))

        match = re.fullmatch(r"/api/projects/([^/]+)/exports/alarms", path)
        if method == "POST" and match:
            project_id = match.group(1)
            ctx = self._require_project(project_id)
            return self._send(201, services.create_alarm_export(ctx, project_id, body))

        match = re.fullmatch(r"/api/projects/([^/]+)/evidence/([^/]+)", path)
        if method == "DELETE" and match:
            project_id, evidence_id = match.groups()
            ctx = self._require_project(project_id)
            services.require_roles(ctx, services.PROJECT_ADMIN_ROLES, "evidence_delete_forbidden", "无权删除证据")
            return self._send(200, services.delete_evidence(ctx, project_id, evidence_id))

        raise services.ApiError(404, "not_found", "接口不存在")

    def serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        safe = path.lstrip("/")
        target = (WEB / safe).resolve()
        if not str(target).startswith(str(WEB.resolve())) or not target.exists() or not target.is_file():
            target = WEB / "index.html"
        content = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    reset = "--reset" in sys.argv
    init_db(reset=reset)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"AI Inspection SaaS MVP running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
