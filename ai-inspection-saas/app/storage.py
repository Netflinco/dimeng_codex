from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data.sqlite3"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def row_to_dict(row: sqlite3.Row | None):
    if row is None:
        return None
    item = dict(row)
    for key, value in list(item.items()):
        if isinstance(value, str) and key.endswith(("Json", "Ids", "Tags", "Permissions")):
            try:
                item[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    return item


def rows_to_dicts(rows):
    return [row_to_dict(row) for row in rows]


def encode(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS tenants (
      id TEXT PRIMARY KEY,
      code TEXT UNIQUE NOT NULL,
      name TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      username TEXT NOT NULL,
      password TEXT NOT NULL,
      name TEXT NOT NULL,
      status TEXT NOT NULL,
      rolesJson TEXT NOT NULL,
      lastLoginAt TEXT,
      UNIQUE(tenantId, username)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      name TEXT NOT NULL,
      city TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS project_members (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      userId TEXT NOT NULL,
      roleIdsJson TEXT NOT NULL,
      dataScope TEXT NOT NULL,
      dataScopeIdsJson TEXT NOT NULL,
      status TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_preferences (
      userId TEXT PRIMARY KEY,
      currentProjectId TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS floors (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      code TEXT NOT NULL,
      name TEXT NOT NULL,
      floorMapId TEXT NOT NULL,
      floorMapVersion INTEGER NOT NULL,
      labelsJson TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS floor_maps (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      floorId TEXT NOT NULL,
      originalFileName TEXT NOT NULL,
      displayImageUrl TEXT,
      floorMapVersion INTEGER NOT NULL,
      mimeType TEXT NOT NULL,
      fileSize INTEGER NOT NULL,
      status TEXT NOT NULL,
      errorMessage TEXT,
      uploadedBy TEXT,
      uploadedAt TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edge_gateways (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      gatewayCode TEXT NOT NULL,
      name TEXT NOT NULL,
      status TEXT NOT NULL,
      lastHeartbeatAt TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS devices (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      deviceCode TEXT NOT NULL,
      deviceName TEXT NOT NULL,
      deviceType TEXT NOT NULL,
      edgeGatewayId TEXT,
      deviceHealthStatus TEXT NOT NULL,
      enabled INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cameras (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      deviceId TEXT NOT NULL,
      streamProtocol TEXT NOT NULL,
      streamAddressRef TEXT NOT NULL,
      mediaStatus TEXT NOT NULL,
      aiCapabilityTagsJson TEXT NOT NULL,
      alarmState TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS device_points (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      floorId TEXT NOT NULL,
      floorMapId TEXT NOT NULL,
      floorMapVersion INTEGER NOT NULL,
      deviceId TEXT NOT NULL,
      deviceType TEXT NOT NULL,
      xRatio REAL NOT NULL,
      yRatio REAL NOT NULL,
      rotation INTEGER NOT NULL,
      scale REAL NOT NULL,
      zIndex INTEGER NOT NULL,
      iconType TEXT NOT NULL,
      visibleOnBigScreen INTEGER NOT NULL,
      version INTEGER NOT NULL,
      UNIQUE(projectId, deviceId)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS media_play_sessions (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      cameraId TEXT NOT NULL,
      protocol TEXT NOT NULL,
      playUrl TEXT NOT NULL,
      expiresAt TEXT NOT NULL,
      status TEXT NOT NULL,
      failureReason TEXT,
      createdBy TEXT NOT NULL,
      createdAt TEXT NOT NULL,
      releasedAt TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inspection_rules (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      name TEXT NOT NULL,
      ruleType TEXT NOT NULL,
      eventType TEXT NOT NULL,
      targetScope TEXT NOT NULL,
      targetIdsJson TEXT NOT NULL,
      excludeDeviceIdsJson TEXT NOT NULL,
      threshold REAL NOT NULL,
      cooldownSeconds INTEGER NOT NULL,
      sourceProvider TEXT NOT NULL,
      modelName TEXT NOT NULL,
      modelVersion TEXT NOT NULL,
      enabled INTEGER NOT NULL,
      hitCount INTEGER NOT NULL,
      alarmCount INTEGER NOT NULL,
      falsePositiveRate REAL NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_events (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      sourceProvider TEXT NOT NULL,
      sourceEventId TEXT NOT NULL,
      idempotencyKey TEXT NOT NULL UNIQUE,
      sourceCameraCode TEXT,
      cameraId TEXT,
      deviceId TEXT,
      eventType TEXT NOT NULL,
      confidence REAL NOT NULL,
      occurredAt TEXT NOT NULL,
      modelName TEXT,
      modelVersion TEXT,
      rawPayloadJson TEXT NOT NULL,
      status TEXT NOT NULL,
      errorCode TEXT,
      errorMessage TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alarms (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      alarmType TEXT NOT NULL,
      level TEXT NOT NULL,
      status TEXT NOT NULL,
      dedupeKey TEXT NOT NULL,
      sourceProvider TEXT NOT NULL,
      sourceEventId TEXT,
      cameraId TEXT NOT NULL,
      deviceId TEXT NOT NULL,
      floorId TEXT,
      area TEXT,
      modelName TEXT,
      modelVersion TEXT,
      confidence REAL NOT NULL,
      riskScore INTEGER NOT NULL,
      evidenceId TEXT,
      occurredAt TEXT NOT NULL,
      slaDeadlineAt TEXT NOT NULL,
      slaStatus TEXT NOT NULL,
      assigneeUserId TEXT,
      assigneeDeptId TEXT,
      falsePositiveReason TEXT,
      closedAt TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alarm_actions (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT NOT NULL,
      alarmId TEXT NOT NULL,
      action TEXT NOT NULL,
      actorUserId TEXT NOT NULL,
      assigneeUserId TEXT,
      assigneeDeptId TEXT,
      remark TEXT,
      idempotencyKey TEXT,
      createdAt TEXT NOT NULL,
      UNIQUE(alarmId, action, idempotencyKey)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
      id TEXT PRIMARY KEY,
      tenantId TEXT NOT NULL,
      projectId TEXT,
      actorUserId TEXT,
      action TEXT NOT NULL,
      objectType TEXT NOT NULL,
      objectId TEXT,
      result TEXT NOT NULL,
      detailJson TEXT NOT NULL,
      createdAt TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS nonces (
      nonce TEXT PRIMARY KEY,
      createdAt TEXT NOT NULL
    )
    """,
]


def init_db(reset: bool = False):
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        for statement in SCHEMA:
            conn.execute(statement)
        seed(conn)


def seed(conn: sqlite3.Connection):
    if conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]:
        return

    conn.execute("INSERT INTO tenants VALUES (?, ?, ?)", ("tenant_001", "joycity-demo", "大悦城商业管理"))
    conn.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("u_operator", "tenant_001", "operator01", "123456", "中控值班员", "active", encode(["operator"]), None),
    )
    conn.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("u_admin", "tenant_001", "admin", "123456", "项目管理员", "active", encode(["project_admin"]), None),
    )
    projects = [
        ("mall_001", "tenant_001", "大悦城示例项目", "上海"),
        ("mall_002", "tenant_001", "虹桥商业裙楼", "上海"),
    ]
    conn.executemany("INSERT INTO projects VALUES (?, ?, ?, ?)", projects)
    members = [
        ("pm_001", "tenant_001", "mall_001", "u_operator", encode(["operator"]), "all", encode([]), "active"),
        ("pm_002", "tenant_001", "mall_001", "u_admin", encode(["project_admin"]), "all", encode([]), "active"),
        ("pm_003", "tenant_001", "mall_002", "u_admin", encode(["project_admin"]), "all", encode([]), "active"),
    ]
    conn.executemany("INSERT INTO project_members VALUES (?, ?, ?, ?, ?, ?, ?, ?)", members)
    conn.execute("INSERT INTO user_preferences VALUES (?, ?)", ("u_operator", "mall_001"))
    conn.execute("INSERT INTO user_preferences VALUES (?, ?)", ("u_admin", "mall_001"))

    labels = {
        "L1": ["主入口", "中庭", "零售区", "消防通道", "扶梯连廊"],
        "B1": ["车行入口", "停车场东区", "停车场西区", "卸货区", "设备通道"],
        "L2": ["北侧零售", "中庭连廊", "南侧零售", "服务通道", "扶梯厅"],
        "L3": ["餐饮入口", "餐饮中庭", "后厨通道", "消防通道", "扶梯厅"],
    }
    for project_id, version in [("mall_001", 3), ("mall_002", 1)]:
        for code in ["L1", "B1", "L2", "L3"]:
            floor_id = f"floor_{project_id}_{code}" if project_id != "mall_001" else f"floor_{code}"
            map_id = f"map_{project_id}_{code}" if project_id != "mall_001" else f"map_{code}"
            conn.execute(
                "INSERT INTO floors VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (floor_id, "tenant_001", project_id, code, f"{code} 楼层", map_id, version, encode(labels[code])),
            )
            conn.execute(
                "INSERT INTO floor_maps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
                (map_id, "tenant_001", project_id, floor_id, "系统默认示意地图", None, version, "system/generated", 0, "active", None, "system"),
            )
    conn.execute(
        "INSERT INTO edge_gateways VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("edge_001", "tenant_001", "mall_001", "EDGE-MALL-01", "中控室边缘网关", "online", "2026-05-09 10:28:00"),
    )

    devices = [
        ("dev_cam_l1_001", "CAM-L1-001", "L1 中庭北侧摄像头", "camera", "online"),
        ("dev_cam_l1_002", "CAM-L1-002", "L1 扶梯口摄像头", "camera", "online"),
        ("dev_cam_l1_003", "CAM-L1-003", "L1 消防通道摄像头", "camera", "online"),
        ("dev_cam_l1_004", "CAM-L1-004", "L1 主入口摄像头", "camera", "online"),
        ("dev_cam_l1_005", "CAM-L1-005", "L1 零售区东侧摄像头", "camera", "online"),
        ("dev_cam_b1_021", "CAM-B1-021", "B1 停车场东区摄像头", "camera", "fault"),
        ("dev_cam_b1_022", "CAM-B1-022", "B1 卸货区摄像头", "camera", "online"),
        ("dev_cam_l3_031", "CAM-L3-031", "L3 餐饮区烟火摄像头", "camera", "online"),
        ("dev_cam_l3_032", "CAM-L3-032", "L3 扶梯厅摄像头", "camera", "online"),
        ("dev_acs_l1_006", "ACS-L1-006", "L1 设备间门禁", "accessControl", "offline"),
        ("dev_sen_l1_011", "SEN-L1-011", "L1 中庭烟感", "sensor", "online"),
        ("dev_sen_b1_012", "SEN-B1-012", "B1 设备通道烟感", "sensor", "online"),
    ]
    for dev_id, code, name, dtype, status in devices:
        conn.execute(
            "INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (dev_id, "tenant_001", "mall_001", code, name, dtype, "edge_001", status, 1),
        )
    camera_rules = {
        "dev_cam_l1_001": ["人员聚集", "通道占用"],
        "dev_cam_l1_002": ["人员聚集"],
        "dev_cam_l1_003": ["通道占用", "烟火识别"],
        "dev_cam_l1_004": ["客流密度"],
        "dev_cam_l1_005": ["异常徘徊"],
        "dev_cam_b1_021": ["违停", "画面异常"],
        "dev_cam_b1_022": ["地面积水", "长时占用"],
        "dev_cam_l3_031": ["烟火识别"],
        "dev_cam_l3_032": ["人员聚集"],
    }
    for index, (device_id, tags) in enumerate(camera_rules.items(), start=1):
        media = "interrupted" if device_id == "dev_cam_b1_021" else "playable"
        alarm_state = "alarming" if device_id in {"dev_cam_l1_002", "dev_cam_l1_003"} else "normal"
        conn.execute(
            "INSERT INTO cameras VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"cam_{index:03d}", "tenant_001", "mall_001", device_id, "RTSP", f"secret://streams/{device_id}", media, encode(tags), alarm_state),
        )

    points = [
        ("dev_cam_l1_001", "floor_L1", 0.34, 0.36, 35),
        ("dev_cam_l1_002", "floor_L1", 0.55, 0.32, 95),
        ("dev_cam_l1_003", "floor_L1", 0.72, 0.57, 180),
        ("dev_cam_l1_004", "floor_L1", 0.18, 0.45, 20),
        ("dev_cam_l1_005", "floor_L1", 0.82, 0.38, 210),
        ("dev_sen_l1_011", "floor_L1", 0.48, 0.46, 0),
        ("dev_cam_b1_021", "floor_B1", 0.28, 0.48, 30),
        ("dev_cam_b1_022", "floor_B1", 0.66, 0.54, 150),
        ("dev_sen_b1_012", "floor_B1", 0.52, 0.35, 0),
        ("dev_cam_l3_031", "floor_L3", 0.42, 0.38, 80),
        ("dev_cam_l3_032", "floor_L3", 0.64, 0.58, 210),
    ]
    for idx, (device_id, floor_id, x, y, rotation) in enumerate(points, start=1):
        device = conn.execute("SELECT deviceType FROM devices WHERE id = ?", (device_id,)).fetchone()
        conn.execute(
            "INSERT INTO device_points VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"point_{idx:03d}", "tenant_001", "mall_001", floor_id, floor_id.replace("floor", "map"), 3, device_id, device["deviceType"], x, y, rotation, 1, 10, "dome-camera", 1, 1),
        )

    rules = [
        ("rule_001", "人员聚集检测", "人员聚集", "crowd", "floor", ["floor_L1"], [], 0.85, 300, "MegviiBox", "CrowdSense", "2.1.0", 1, 128, 21, 0.084),
        ("rule_002", "消防通道占用", "消防通道占用", "blocked_passage", "device", ["dev_cam_l1_003"], [], 0.9, 600, "MegviiBox", "PassageGuard", "1.8.4", 1, 42, 9, 0.031),
        ("rule_003", "画面异常", "画面异常", "video_abnormal", "project", ["mall_001"], [], 0.8, 900, "EdgeVision", "StreamHealth", "3.0.2", 1, 78, 14, 0.12),
    ]
    conn.executemany("INSERT INTO inspection_rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        (rid, "tenant_001", "mall_001", name, rtype, etype, scope, encode(ids), encode(ex), threshold, cooldown, provider, model, version, enabled, hit, alarm, fp)
        for rid, name, rtype, etype, scope, ids, ex, threshold, cooldown, provider, model, version, enabled, hit, alarm, fp in rules
    ])

    alarms = [
        ("alm_001", "人员聚集", "P2", "待确认", "rule_001:dev_cam_l1_002:lobby", "MegviiBox", "cam_002", "dev_cam_l1_002", "floor_L1", "扶梯连廊", 0.91, 82, "2026-05-09 10:24:31", "2026-05-09 10:54:31", "normal"),
        ("alm_002", "消防通道占用", "P1", "已确认", "rule_002:dev_cam_l1_003:passage", "MegviiBox", "cam_003", "dev_cam_l1_003", "floor_L1", "消防通道", 0.94, 96, "2026-05-09 10:18:09", "2026-05-09 10:28:09", "overdue"),
        ("alm_003", "画面异常", "P3", "处理中", "rule_003:dev_cam_b1_021:stream", "EdgeVision", "cam_006", "dev_cam_b1_021", "floor_B1", "停车场东区", 0.86, 63, "2026-05-09 09:52:44", "2026-05-09 11:52:44", "normal"),
    ]
    for idx, alarm in enumerate(alarms, start=1):
        conn.execute(
            "INSERT INTO alarms VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (alarm[0], "tenant_001", "mall_001", alarm[1], alarm[2], alarm[3], alarm[4], alarm[5], None, alarm[6], alarm[7], alarm[8], alarm[9], "model", "v1", alarm[10], alarm[11], f"evd_{idx:03d}", alarm[12], alarm[13], alarm[14], None, None, None, None),
        )
    conn.commit()
