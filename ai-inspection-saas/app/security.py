from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from .storage import connect, row_to_dict

SESSION_TTL_SECONDS = 8 * 60 * 60
sessions: dict[str, dict] = {}


@dataclass
class AuthContext:
    token: str
    tenantId: str
    userId: str
    username: str
    name: str
    roles: list[str]


def create_session(user: dict) -> str:
    token = secrets.token_urlsafe(32)
    sessions[token] = {
        "tenantId": user["tenantId"],
        "userId": user["id"],
        "username": user["username"],
        "name": user["name"],
        "roles": json.loads(user["rolesJson"]) if isinstance(user["rolesJson"], str) else user["rolesJson"],
        "expiresAt": time.time() + SESSION_TTL_SECONDS,
    }
    return token


def get_context(headers) -> AuthContext | None:
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    session = sessions.get(token)
    if not session or session["expiresAt"] < time.time():
        sessions.pop(token, None)
        return None
    return AuthContext(
        token=token,
        tenantId=session["tenantId"],
        userId=session["userId"],
        username=session["username"],
        name=session["name"],
        roles=session["roles"],
    )


def require_project(ctx: AuthContext, project_id: str):
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM project_members
            WHERE tenantId = ? AND projectId = ? AND userId = ? AND status = 'active'
            """,
            (ctx.tenantId, project_id, ctx.userId),
        ).fetchone()
    if not row:
        return None
    return row_to_dict(row)


def body_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def verify_webhook_signature(method: str, path: str, body: bytes, headers, secret: str) -> tuple[bool, str | None]:
    app_key = headers.get("X-App-Key")
    timestamp = headers.get("X-Timestamp")
    nonce = headers.get("X-Nonce")
    signature = headers.get("X-Signature")
    if not all([app_key, timestamp, nonce, signature]):
        return False, "missing_signature_headers"
    try:
        ts = int(timestamp)
    except ValueError:
        return False, "invalid_timestamp"
    if abs(int(time.time()) - ts) > 300:
        return False, "timestamp_expired"
    with connect() as conn:
        exists = conn.execute("SELECT nonce FROM nonces WHERE nonce = ?", (nonce,)).fetchone()
        if exists:
            return False, "nonce_replay"
        canonical = "\n".join([method.upper(), path, timestamp, nonce, body_hash(body)])
        expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return False, "bad_signature"
        conn.execute("INSERT INTO nonces VALUES (?, datetime('now'))", (nonce,))
        conn.commit()
    return True, None
