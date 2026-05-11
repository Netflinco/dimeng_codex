const state = {
  token: localStorage.getItem("ais_token"),
  user: JSON.parse(localStorage.getItem("ais_user") || "null"),
  currentProjectId: localStorage.getItem("ais_project"),
  projects: [],
  route: localStorage.getItem("ais_token") ? "dashboard" : "login",
  floors: [],
  activeSessions: [],
};

const app = document.querySelector("#app");
const ADMIN_ROUTES = new Set(["map", "rules", "audit"]);

function isProjectAdmin() {
  const roles = new Set(state.user?.roles || []);
  const project = state.projects.find((item) => item.id === state.currentProjectId);
  (project?.roleIdsJson || []).forEach((role) => roles.add(role));
  return roles.has("project_admin") || roles.has("system_admin");
}

function navItems() {
  const items = ["dashboard:指挥中心", "cameras:摄像头管理", "map:点位配置", "alarms:告警查询", "rules:规则配置", "audit:审计日志"];
  if (isProjectAdmin()) return items;
  return items.filter((item) => !ADMIN_ROUTES.has(item.split(":")[0]));
}

function adminMenuItems() {
  const base = ["cameras:摄像头管理", "alarms:告警查询"];
  const admin = ["map:点位配置", "rules:规则配置", "audit:审计日志"];
  return (isProjectAdmin() ? [...base, ...admin] : base);
}

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const res = await fetch(path, { ...options, headers, body: options.body ? JSON.stringify(options.body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || data.code || "请求失败");
  return data;
}

function toast(message) {
  let node = document.querySelector(".toast");
  if (!node) {
    node = document.createElement("div");
    node.className = "toast";
    document.body.appendChild(node);
  }
  node.textContent = message;
  node.classList.add("show");
  setTimeout(() => node.classList.remove("show"), 2200);
}

function statusText(value) {
  return {
    online: "在线", offline: "离线", fault: "故障", playable: "可预览",
    interrupted: "断流", authFailed: "鉴权失败", transcoding: "转码中",
    normal: "正常", alarming: "告警中", configured: "已配置", unconfigured: "未配置",
    active: "当前生效", archived: "已归档", processing: "转换中", failed: "失败",
    camera: "摄像头", sensor: "传感器", accessControl: "门禁"
  }[value] || value;
}

function pointIcon(type) {
  if (type === "camera") return "CAM";
  if (type === "sensor") return "SEN";
  if (type === "accessControl") return "ACS";
  return "DEV";
}

function shortDeviceLabel(name = "") {
  return name
    .replace(/^[BL]\d\s*/, "")
    .replace(/摄像头|烟感|门禁/g, "")
    .replace(/北侧|东侧/g, "")
    .trim()
    .slice(0, 6);
}

function formatBytes(size = 0) {
  if (!size) return "0 KB";
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${Math.round(size / 1024 / 1024 * 10) / 10} MB`;
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  }[char]));
}

function dashboardMapFloors() {
  return (state.floors || []).filter((floor) => !floor.floorMapStatus || floor.floorMapStatus === "active");
}

function dashboardFloorKey() {
  return `ais_dashboard_floor_${state.currentProjectId}`;
}

function currentDashboardFloor() {
  const floors = dashboardMapFloors();
  const saved = localStorage.getItem(dashboardFloorKey());
  return floors.find((floor) => floor.code === saved || floor.id === saved) || floors.find((floor) => floor.code === "L1") || floors[0] || { code: "L1", name: "L1 楼层" };
}

function dashboardFloorSwitcher(floors, selectedFloor) {
  if (floors.length <= 1) return "";
  return `
    <div class="floor-switch" aria-label="楼层地图切换">
      ${floors.map((floor) => {
        const code = floor.code || floor.id;
        return `<button class="${code === selectedFloor.code ? "active" : ""}" data-dashboard-floor="${code}" title="${floor.name || code}">${code}</button>`;
      }).join("")}
    </div>`;
}

function alarmMatchesInspection(alarm, inspectionName) {
  const alarmType = alarm.alarmType || "";
  return alarmType === inspectionName || alarmType.includes(inspectionName) || inspectionName.includes(alarmType);
}

function aiInspectionGroups(cameras = [], activeAlarms = []) {
  const groups = new Map();
  const ensureGroup = (name) => {
    const key = name || "未归类巡检";
    if (!groups.has(key)) groups.set(key, { name: key, cameraNames: [], alarms: [] });
    return groups.get(key);
  };

  cameras.forEach((camera) => {
    (camera.aiCapabilityTagsJson || []).forEach((tag) => {
      const group = ensureGroup(tag);
      const cameraName = camera.deviceName || camera.deviceCode || "未知摄像头";
      if (!group.cameraNames.includes(cameraName)) group.cameraNames.push(cameraName);
    });
  });

  activeAlarms.forEach((alarm) => {
    let group = [...groups.values()].find((item) => alarmMatchesInspection(alarm, item.name));
    if (!group) group = ensureGroup(alarm.alarmType || "未归类告警");
    group.alarms.push(alarm);
    const alarmCameraName = alarm.deviceName || alarm.deviceCode;
    if (alarmCameraName && !group.cameraNames.includes(alarmCameraName)) group.cameraNames.push(alarmCameraName);
  });

  return [...groups.values()].sort((a, b) =>
    b.alarms.length - a.alarms.length ||
    b.cameraNames.length - a.cameraNames.length ||
    a.name.localeCompare(b.name, "zh-Hans-CN")
  );
}

function renderAiInspectionStatus(cameras, activeAlarms) {
  const groups = aiInspectionGroups(cameras, activeAlarms);
  const hasActiveAlarm = groups.some((group) => group.alarms.length);
  if (!groups.length) return `<div class="screen-empty">当前项目暂无 AI 巡检项</div>`;

  return `
    <div class="ai-inspection-list">
      ${groups.map((group, index) => {
        const expanded = group.alarms.length > 0 || (!hasActiveAlarm && index < 2);
        const cameraCount = group.cameraNames.length;
        const cameraNames = cameraCount ? group.cameraNames : ["暂无摄像头明细"];
        return `
          <article class="ai-inspection-card ${expanded ? "expanded" : ""} ${group.alarms.length ? "has-alert" : ""}">
            <button class="ai-inspection-head" data-ai-status-toggle>
              <span>
                <strong>${escapeHtml(group.name)}</strong>
                <em>${cameraCount} 路摄像头</em>
              </span>
              <span class="ai-inspection-meta">
                ${group.alarms.length ? `<b>${group.alarms.length} 个实时告警</b>` : `<b class="quiet">运行中</b>`}
                <i>${expanded ? "收起" : "展开"}</i>
              </span>
            </button>
            <div class="ai-camera-list">
              ${cameraNames.map((name) => `<span title="${escapeHtml(name)}">${escapeHtml(name)}</span>`).join("")}
            </div>
            ${group.alarms.length ? `
              <div class="ai-alarm-line">
                ${group.alarms.slice(0, 2).map((alarm) => `<span class="${alarm.level}">${escapeHtml(alarm.level)} · ${escapeHtml(alarm.status)} · ${escapeHtml(alarm.floorCode || "")}${escapeHtml(alarm.area || "")}</span>`).join("")}
              </div>` : ""}
          </article>`;
      }).join("")}
    </div>`;
}

async function bootstrap() {
  if (!state.token) return render();
  try {
    const data = await api("/api/me/projects");
    state.projects = data.projects;
    const allowedProjectIds = new Set(data.projects.map((project) => project.id));
    state.currentProjectId = allowedProjectIds.has(state.currentProjectId) ? state.currentProjectId : (data.currentProjectId || data.projects[0]?.id);
    localStorage.setItem("ais_project", state.currentProjectId);
    state.floors = (await api(`/api/projects/${state.currentProjectId}/floors`)).floors;
  } catch {
    localStorage.removeItem("ais_token");
    localStorage.removeItem("ais_project");
    localStorage.removeItem("ais_user");
    state.token = null;
    state.user = null;
    state.route = "login";
  }
  render();
}

function shell(content) {
  app.innerHTML = `
    <div class="shell">
      <aside class="side">
        <div class="brand">智巡中枢</div>
        <div class="nav">
          ${navItems().map((item) => {
            const [route, label] = item.split(":");
            return `<button class="${state.route === route ? "active" : ""}" data-route="${route}">${label}</button>`;
          }).join("")}
        </div>
        <button class="ghost" data-logout>退出登录</button>
      </aside>
      <main class="main">
        <div class="topbar">
          <h1>${titleForRoute()}</h1>
          <div class="top-actions">
            <select data-project>
              ${state.projects.map((p) => `<option value="${p.id}" ${p.id === state.currentProjectId ? "selected" : ""}>${p.name}</option>`).join("")}
            </select>
            <span>${new Date().toLocaleString("zh-CN", { hour12: false })}</span>
          </div>
        </div>
        ${content}
      </main>
    </div>
  `;
  document.querySelectorAll("[data-route]").forEach((btn) => btn.onclick = () => { state.route = btn.dataset.route; render(); });
  document.querySelector("[data-logout]").onclick = () => {
    localStorage.removeItem("ais_token"); localStorage.removeItem("ais_project");
    localStorage.removeItem("ais_user");
    state.token = null; state.user = null; state.route = "login"; render();
  };
  document.querySelector("[data-project]").onchange = async (event) => switchProject(event.target.value);
}

function dashboardShell(content, summary) {
  const project = summary.project || {};
  app.innerHTML = `
    <main class="screen">
      <header class="screen-header">
        <div class="screen-title">
          <span>AI VIDEO INSPECTION COMMAND CENTER</span>
          <h1>${project.name || "指挥中心"}</h1>
        </div>
        <div class="screen-status">
          <div class="live-dot">实时态势</div>
          <select data-project class="screen-project">
            ${state.projects.map((p) => `<option value="${p.id}" ${p.id === state.currentProjectId ? "selected" : ""}>${p.name}</option>`).join("")}
          </select>
          <div class="admin-entry">
            <button class="screen-admin-btn" data-admin-toggle>管理入口</button>
            <div class="admin-menu" data-admin-menu>
              ${adminMenuItems().map((item) => {
                const [route, label] = item.split(":");
                return `<button data-admin-route="${route}">${label}</button>`;
              }).join("")}
            </div>
          </div>
          <strong>${new Date().toLocaleString("zh-CN", { hour12: false })}</strong>
        </div>
      </header>
      ${content}
    </main>
  `;
  document.querySelector("[data-project]").onchange = async (event) => switchProject(event.target.value);
  document.querySelector("[data-admin-toggle]").onclick = () => {
    document.querySelector("[data-admin-menu]").classList.toggle("show");
  };
  document.querySelectorAll("[data-admin-route]").forEach((button) => {
    button.onclick = () => {
      state.route = button.dataset.adminRoute;
      document.querySelector("[data-admin-menu]").classList.remove("show");
      render();
    };
  });
}

function titleForRoute() {
  return { dashboard: "指挥中心", cameras: "摄像头管理", map: "设备点位配置", alarms: "告警查询", rules: "平台规则配置", audit: "审计日志" }[state.route] || "";
}

async function switchProject(projectId) {
  await Promise.allSettled(state.activeSessions.map((id) => api(`/api/media/play-sessions/${id}`, { method: "DELETE" })));
  state.activeSessions = [];
  app.innerHTML = `<main class="screen"><div class="screen-empty">正在切换项目...</div></main>`;
  await api("/api/me/preferences/current-project", { method: "POST", body: { projectId } });
  state.currentProjectId = projectId;
  localStorage.setItem("ais_project", projectId);
  state.floors = (await api(`/api/projects/${projectId}/floors`)).floors;
  toast("项目已切换，旧视频会话和页面缓存已清理");
  render();
}

function renderLogin() {
  app.innerHTML = `
    <main class="login">
      <section>
        <h1>商业空间 AI 视频巡检与告警闭环平台</h1>
        <p>统一接入摄像头、第三方 AI 事件、设备点位和告警证据，用项目级权限隔离与人工确认机制控制误报影响。</p>
        <div class="hero-map"><div class="wing w1"></div><div class="wing w2"></div><div class="wing w3"></div><i class="pin p1"></i><i class="pin p2"></i><i class="pin p3"></i></div>
      </section>
      <section class="login-card">
        <h2>登录智巡中枢</h2>
        <p style="color:var(--muted)">示例账号：operator01 / 123456，或 admin / 123456</p>
        <div class="field"><label>企业编码</label><input id="tenant" value="joycity-demo"></div>
        <div class="field"><label>账号</label><input id="username" value="operator01"></div>
        <div class="field"><label>密码</label><input id="password" type="password" value="123456"></div>
        <div class="error" data-error></div>
        <button class="primary" style="width:100%" data-login>进入系统</button>
      </section>
    </main>
  `;
  document.querySelector("[data-login]").onclick = async () => {
    try {
      const data = await api("/api/auth/login", {
        method: "POST",
        body: {
          tenantCode: document.querySelector("#tenant").value,
          username: document.querySelector("#username").value,
          password: document.querySelector("#password").value,
        },
      });
      state.token = data.token;
      state.user = data.user;
      state.projects = data.projects;
      const allowedProjectIds = new Set(data.projects.map((project) => project.id));
      state.currentProjectId = allowedProjectIds.has(data.currentProjectId) ? data.currentProjectId : data.projects[0]?.id;
      localStorage.setItem("ais_token", state.token);
      localStorage.setItem("ais_user", JSON.stringify(state.user));
      localStorage.setItem("ais_project", state.currentProjectId);
      state.route = "dashboard";
      await bootstrap();
    } catch (err) {
      document.querySelector("[data-error]").textContent = err.message;
    }
  };
}

async function renderDashboard() {
  const mapFloors = dashboardMapFloors();
  const selectedFloor = currentDashboardFloor();
  const floorId = selectedFloor.code || selectedFloor.id || "L1";
  const [summary, alarms, points, cameraData] = await Promise.all([
    api(`/api/projects/${state.currentProjectId}/summary`),
    api(`/api/projects/${state.currentProjectId}/alarms`),
    api(`/api/projects/${state.currentProjectId}/points?floorId=${encodeURIComponent(floorId)}`),
    api(`/api/projects/${state.currentProjectId}/cameras`),
  ]);
  const activeAlarms = alarms.alarms.filter((alarm) => alarm.status !== "已关闭");
  const displayFloor = points.floor || selectedFloor;
  const displayFloorCode = displayFloor.code || floorId;
  dashboardShell(`
    <section class="screen-metrics">
      <div><span>摄像头在线率</span><strong>${summary.cameraOnlineRate}%</strong><em>Edge Gateway 正常</em></div>
      <div><span>今日告警</span><strong>${summary.todayAlarms}</strong><em>AI 事件 ${summary.aiEventsToday}</em></div>
      <div><span>待处理</span><strong>${summary.pendingAlarms}</strong><em>P1 优先响应</em></div>
      <div><span>SLA 达标</span><strong>${summary.slaPassRate}%</strong><em>近 24 小时</em></div>
    </section>
    <section class="screen-grid">
      <aside class="screen-panel ai-status-panel">
        <h2>AI 接入状态</h2>
        ${renderAiInspectionStatus(cameraData.cameras || [], activeAlarms)}
      </aside>
      <section class="screen-map-panel">
        <div class="map-head">
          <div><span>PROJECT FLOOR</span><strong>${displayFloorCode} 三维楼层态势</strong></div>
          <div class="map-tools">
            ${dashboardFloorSwitcher(mapFloors, displayFloor)}
            <div class="map-legend"><i></i>在线 <i class="alarm"></i>告警 <i class="offline"></i>离线/故障</div>
          </div>
        </div>
        ${dashboardMap3d(points.floor.labelsJson || points.floor.labels || [], points.points)}
      </section>
      <aside class="screen-panel">
        <h2>视频轮巡</h2>
        <div class="screen-videos">${points.points.filter((p) => p.cameraId).length ? points.points.filter((p) => p.cameraId).slice(0,3).map((p) => `
          <div class="screen-video"><span>LIVE</span><strong>${p.deviceName}</strong><em>Media Gateway WebRTC</em></div>`).join("") : `<div class="screen-empty">暂无可轮巡视频</div>`}</div>
        <h2>风险区域排行</h2>
        <div class="risk-list">
          <div><strong>扶梯连廊</strong><span>近 24 小时 12 次</span></div>
          <div><strong>消防通道</strong><span>近 24 小时 7 次</span></div>
          <div><strong>停车场东区</strong><span>近 24 小时 5 次</span></div>
        </div>
      </aside>
    </section>
    <section class="screen-footer">
      <div><span>告警趋势</span><b style="width:72%"></b><b style="width:48%"></b><b style="width:62%"></b><b style="width:36%"></b></div>
      <div><span>类型分布</span><strong>人员聚集 38%</strong><strong>通道占用 26%</strong><strong>画面异常 18%</strong></div>
    </section>
  `, summary);
  document.querySelectorAll("[data-dashboard-floor]").forEach((button) => {
    button.onclick = () => {
      localStorage.setItem(dashboardFloorKey(), button.dataset.dashboardFloor);
      renderDashboard();
    };
  });
  document.querySelectorAll("[data-ai-status-toggle]").forEach((button) => {
    button.onclick = () => {
      const card = button.closest(".ai-inspection-card");
      const expanded = card.classList.toggle("expanded");
      button.querySelector("i").textContent = expanded ? "收起" : "展开";
    };
  });
}

function floorMap(labels, points, mapInfo = null, draggable = false) {
  const zones = ["z1", "z2", "z3", "z4", "z5"].map((z, i) => `<div class="zone ${z}">${labels[i] || ""}</div>`).join("");
  const nodes = points.map((p) => `<div class="point ${p.alarmState === "alarming" ? "alarming" : p.deviceHealthStatus}" data-device-id="${p.deviceId}" style="left:${p.xRatio * 100}%;top:${p.yRatio * 100}%">${pointIcon(p.deviceType)}</div>`).join("");
  const imageStyle = mapInfo?.displayImageUrl ? ` style="background-image:linear-gradient(rgba(238,246,251,.74), rgba(238,246,251,.74)), url('${mapInfo.displayImageUrl}')"` : "";
  return `<div class="floor-wrap"><div class="floor-map ${mapInfo?.displayImageUrl ? "with-uploaded-map" : ""}" data-floor-map${imageStyle}>${zones}${nodes}</div></div>`;
}

function dashboardMap3d(labels, points) {
  const zones = ["z1", "z2", "z3", "z4", "z5"].map((z, i) => `
    <div class="zone3d ${z}">
      <span>${labels[i] || ""}</span>
    </div>`).join("");
  const nodes = points.map((p, index) => {
    const status = p.alarmState === "alarming" ? "alarming" : p.deviceHealthStatus;
    return `
      <div class="point3d ${status} label-${index % 6}" style="left:${p.xRatio * 100}%;top:${p.yRatio * 100}%">
        <i></i><strong>${pointIcon(p.deviceType)}</strong><span>${shortDeviceLabel(p.deviceName)}</span>
      </div>`;
  }).join("");
  return `
    <div class="map3d-stage">
      <div class="scan-beam"></div>
      <div class="floor3d" data-floor-map>
        <div class="floor-grid"></div>
        ${zones}
        ${nodes}
      </div>
      ${points.length ? "" : `<div class="map-empty">当前楼层暂无点位</div>`}
    </div>`;
}

function cameraRecentAlarms(camera, alarms = []) {
  return alarms
    .filter((alarm) => alarm.deviceCode === camera.deviceCode || alarm.deviceName === camera.deviceName)
    .slice(0, 3);
}

function renderCameraDetail(camera, alarms = []) {
  if (!camera) {
    return `<h3>摄像头详情</h3><p style="color:var(--muted)">当前项目暂无摄像头。</p>`;
  }
  const recentAlarms = cameraRecentAlarms(camera, alarms);
  return `
    <div class="detail-kicker">摄像头详情</div>
    <h3>${escapeHtml(camera.deviceName)}</h3>
    <div class="camera-preview">
      <span>${escapeHtml(statusText(camera.mediaStatus))}</span>
      <strong>${escapeHtml(camera.streamProtocol)}</strong>
      <em>源流地址已脱敏</em>
    </div>
    <div class="detail-actions">
      <button class="ghost" data-detail-preview="${camera.id}">预览视频</button>
      <button class="ghost" data-detail-locate="${camera.id}">查看点位</button>
    </div>
    <section class="detail-section">
      <h4>基础信息</h4>
      <div class="kv"><span>设备编号</span><strong>${escapeHtml(camera.deviceCode)}</strong></div>
      <div class="kv"><span>楼层区域</span><strong>${escapeHtml(camera.location?.label || "未配置")}</strong></div>
      <div class="kv"><span>设备类型</span><strong>${escapeHtml(statusText(camera.deviceType || "camera"))}</strong></div>
    </section>
    <section class="detail-section">
      <h4>运行状态</h4>
      <div class="detail-status-grid">
        <div><span>设备</span><b class="${camera.deviceHealthStatus}">${escapeHtml(statusText(camera.deviceHealthStatus))}</b></div>
        <div><span>媒体</span><b class="${camera.mediaStatus}">${escapeHtml(statusText(camera.mediaStatus))}</b></div>
        <div><span>点位</span><b>${escapeHtml(statusText(camera.pointConfigStatus))}</b></div>
      </div>
    </section>
    <section class="detail-section">
      <h4>AI 能力</h4>
      <div class="detail-tags">
        ${(camera.aiCapabilityTagsJson || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("") || `<span>未配置</span>`}
      </div>
    </section>
    <section class="detail-section">
      <h4>近期告警</h4>
      <div class="detail-alarms">
        ${recentAlarms.length ? recentAlarms.map((alarm) => `
          <div>
            <b class="${alarm.level}">${escapeHtml(alarm.level)}</b>
            <span>${escapeHtml(alarm.alarmType)} · ${escapeHtml(alarm.status)}</span>
            <em>${escapeHtml(alarm.occurredAt || "")}</em>
          </div>`).join("") : `<p>近期待处理告警为空。</p>`}
      </div>
    </section>`;
}

async function renderCameras() {
  const [data, alarmData] = await Promise.all([
    api(`/api/projects/${state.currentProjectId}/cameras`),
    api(`/api/projects/${state.currentProjectId}/alarms`),
  ]);
  const selectedCamera = data.cameras[0];
  shell(`
    <div class="split">
      <table class="table">
        <thead><tr><th>摄像头</th><th>点位楼层/区域</th><th>设备状态</th><th>媒体状态</th><th>AI 能力</th><th>操作</th></tr></thead>
        <tbody>${data.cameras.map((c) => `
          <tr data-camera="${c.id}" class="${selectedCamera?.id === c.id ? "selected-row" : ""}">
            <td><strong>${escapeHtml(c.deviceName)}</strong><br><small>${escapeHtml(c.deviceCode)}</small></td>
            <td>${escapeHtml(c.location.label)}</td>
            <td><span class="status ${c.deviceHealthStatus}">${statusText(c.deviceHealthStatus)}</span></td>
            <td><span class="status ${c.mediaStatus}">${statusText(c.mediaStatus)}</span></td>
            <td>${c.aiCapabilityTagsJson.map((tag) => `<span class="status">${escapeHtml(tag)}</span>`).join(" ")}</td>
            <td><button class="ghost" data-preview="${c.id}">预览</button> <button class="ghost" data-locate>定位</button></td>
          </tr>`).join("")}</tbody>
      </table>
      <aside class="panel drawer camera-detail" data-drawer>${renderCameraDetail(selectedCamera, alarmData.alarms)}</aside>
    </div>
  `);
  const selectCamera = (cameraId) => {
    const c = data.cameras.find((item) => item.id === cameraId);
    if (!c) return;
    document.querySelectorAll("[data-camera]").forEach((item) => item.classList.toggle("selected-row", item.dataset.camera === cameraId));
    document.querySelector("[data-drawer]").innerHTML = renderCameraDetail(c, alarmData.alarms);
  };
  const previewCamera = async (cameraId) => {
    const session = await api(`/api/projects/${state.currentProjectId}/media/play-sessions`, { method: "POST", body: { cameraId } });
    state.activeSessions.push(session.sessionId);
    toast(session.failureReason ? `播放失败：${statusText(session.failureReason)}` : "已获取短时播放会话");
  };
  document.querySelectorAll("[data-camera]").forEach((row) => row.onclick = () => selectCamera(row.dataset.camera));
  document.querySelectorAll("[data-preview]").forEach((btn) => btn.onclick = async (event) => {
    event.stopPropagation();
    selectCamera(btn.dataset.preview);
    await previewCamera(btn.dataset.preview);
  });
  document.querySelectorAll("[data-locate]").forEach((btn) => btn.onclick = (event) => { event.stopPropagation(); state.route = "map"; render(); });
  document.querySelector("[data-drawer]").onclick = async (event) => {
    const preview = event.target.closest("[data-detail-preview]");
    const locate = event.target.closest("[data-detail-locate]");
    if (preview) await previewCamera(preview.dataset.detailPreview);
    if (locate) { state.route = "map"; render(); }
  };
}

async function renderMapConfig() {
  const floor = window.currentFloor || "L1";
  const [cameraData, pointData] = await Promise.all([
    api(`/api/projects/${state.currentProjectId}/cameras`),
    api(`/api/projects/${state.currentProjectId}/points?floorId=${floor}`),
  ]);
  const pointIds = new Set(pointData.points.map((p) => p.deviceId));
  shell(`
    <div class="three">
      <aside class="panel"><h3>摄像头资产</h3><div class="device-list">${cameraData.cameras.map((c) => {
        const configuredHere = pointIds.has(c.deviceId);
        return `<div class="device-card" draggable="${!configuredHere}" data-device-card="${c.deviceId}">
          <strong>${c.deviceName}</strong>
          <small>${configuredHere ? c.location.label : "未配置到当前楼层"}</small>
          ${configuredHere ? `<button class="danger mini-btn" data-remove-device="${c.deviceId}">移除点位</button>` : ""}
        </div>`;
      }).join("")}</div></aside>
      <section class="panel">
        <div class="toolbar">
          <select data-floor-picker>${state.floors.map((f) => `<option value="${f.code}" ${f.code === floor ? "selected" : ""}>${f.code} ${f.name}</option>`).join("")}</select>
          <button class="primary" data-save-points>保存当前楼层</button>
        </div>
        <div class="map-maintenance">
          <div class="map-file-summary">
            <strong>楼层地图文件</strong>
            <span>${pointData.floor.map?.originalFileName || "系统默认示意地图"} · v${pointData.floor.floorMapVersion} · ${statusText(pointData.floor.map?.status || "active")} · ${formatBytes(pointData.floor.map?.fileSize || 0)}</span>
          </div>
          <div class="map-upload-controls">
            <input data-map-file type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml">
            <button class="ghost" data-upload-map>上传/替换地图</button>
          </div>
          <p class="map-upload-tip">支持 PNG、JPG/JPEG、WebP、SVG，单文件不超过 20MB。建议上传商场楼层平面图、CAD 导出图或实施图纸；SVG 不可包含脚本、事件属性或外链资源。替换地图后版本会递增，已有点位需复核位置。</p>
        </div>
        ${floorMap(pointData.floor.labelsJson || pointData.floor.labels || [], pointData.points, pointData.floor.map, true)}
      </section>
    </div>
  `);
  const map = document.querySelector("[data-floor-map]");
  let draft = pointData.points.map((p) => ({ deviceId: p.deviceId, xRatio: p.xRatio, yRatio: p.yRatio, rotation: p.rotation, version: p.version }));
  document.querySelector("[data-floor-picker]").onchange = (e) => { window.currentFloor = e.target.value; renderMapConfig(); };
  document.querySelector("[data-upload-map]").onclick = async () => {
    const file = document.querySelector("[data-map-file]").files[0];
    if (!file) {
      toast("请先选择 PNG、JPG、WebP 或 SVG 楼层图");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      toast("地图文件不能超过 20MB");
      return;
    }
    try {
      const dataUrl = await readFileAsDataUrl(file);
      await api(`/api/projects/${state.currentProjectId}/floors/${floor}/map`, {
        method: "POST",
        body: { fileName: file.name, mimeType: file.type, dataUrl },
      });
      toast("地图已上传，楼层图版本已更新");
      state.floors = (await api(`/api/projects/${state.currentProjectId}/floors`)).floors;
      renderMapConfig();
    } catch (err) {
      toast(err.message);
    }
  };
  document.querySelectorAll("[data-device-card]").forEach((card) => {
    card.ondragstart = (e) => e.dataTransfer.setData("text/plain", card.dataset.deviceCard);
  });
  document.querySelectorAll("[data-remove-device]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      draft = draft.filter((point) => point.deviceId !== button.dataset.removeDevice);
      drawDraft(map, draft, cameraData.cameras);
      toast("点位已移除，请保存当前楼层");
    };
  });
  map.ondragover = (e) => e.preventDefault();
  map.ondrop = (e) => {
    e.preventDefault();
    const deviceId = e.dataTransfer.getData("text/plain");
    if (!deviceId || draft.some((p) => p.deviceId === deviceId)) return;
    draft.push({ deviceId, ...relative(e, map), rotation: 0, version: 1 });
    toast("已放置点位，请保存当前楼层");
    drawDraft(map, draft, cameraData.cameras);
  };
  enablePointDrag(map, draft, cameraData.cameras);
  document.querySelector("[data-save-points]").onclick = async () => {
    const saved = await api(`/api/projects/${state.currentProjectId}/points/floors/${floor}`, { method: "PUT", body: { floorMapVersion: pointData.floor.floorMapVersion, points: draft } });
    toast(`已保存 ${saved.points.length} 个点位`);
    renderMapConfig();
  };
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("读取地图文件失败"));
    reader.readAsDataURL(file);
  });
}

function relative(e, el) {
  const rect = el.getBoundingClientRect();
  return { xRatio: Math.min(.98, Math.max(.02, (e.clientX - rect.left) / rect.width)), yRatio: Math.min(.98, Math.max(.02, (e.clientY - rect.top) / rect.height)) };
}

function drawDraft(map, draft, cameras) {
  map.querySelectorAll(".point").forEach((p) => p.remove());
  draft.forEach((p) => {
    const c = cameras.find((item) => item.deviceId === p.deviceId);
    const node = document.createElement("div");
    node.className = `point ${c?.deviceHealthStatus || "online"}`;
    node.dataset.deviceId = p.deviceId;
    node.style.left = `${p.xRatio * 100}%`;
    node.style.top = `${p.yRatio * 100}%`;
    node.textContent = "CAM";
    map.appendChild(node);
  });
  enablePointDrag(map, draft, cameras);
}

function enablePointDrag(map, draft, cameras) {
  map.querySelectorAll(".point").forEach((node) => {
    node.onpointerdown = (e) => {
      e.preventDefault(); node.setPointerCapture(e.pointerId); node.classList.add("selected");
      const move = (ev) => { const next = relative(ev, map); node.style.left = `${next.xRatio * 100}%`; node.style.top = `${next.yRatio * 100}%`; };
      const up = (ev) => {
        const next = relative(ev, map);
        draft.splice(draft.findIndex((p) => p.deviceId === node.dataset.deviceId), 1, { ...draft.find((p) => p.deviceId === node.dataset.deviceId), ...next });
        node.releasePointerCapture(ev.pointerId); node.onpointermove = null; node.onpointerup = null;
      };
      node.onpointermove = move; node.onpointerup = up;
    };
    node.onclick = () => toast("拖动点位可调整坐标，移除点位请在左侧摄像头资产中操作");
  });
}

async function renderAlarms() {
  const data = await api(`/api/projects/${state.currentProjectId}/alarms`);
  shell(`
    <div class="split">
      <table class="table"><thead><tr><th>告警</th><th>等级</th><th>位置</th><th>状态</th><th>SLA</th></tr></thead>
      <tbody>${data.alarms.map((a) => `<tr data-alarm="${a.id}"><td><strong>${a.alarmType}</strong><br><small>${a.id} · ${a.occurredAt}</small></td><td><span class="status ${a.level}">${a.level}</span></td><td>${a.floorCode || ""} / ${a.area || ""}</td><td>${a.status}</td><td>${a.slaStatus}</td></tr>`).join("")}</tbody></table>
      <aside class="panel drawer" data-alarm-detail><h3>告警详情</h3><p style="color:var(--muted)">选择一条告警。</p></aside>
    </div>`);
  document.querySelectorAll("[data-alarm]").forEach((row) => row.onclick = () => showAlarm(row.dataset.alarm));
  if (data.alarms[0]) showAlarm(data.alarms[0].id);
}

async function showAlarm(id) {
  const a = await api(`/api/projects/${state.currentProjectId}/alarms/${id}`);
  const actions = { "待确认": ["confirm", "markFalsePositive"], "已确认": ["assign", "start"], "已指派": ["assign", "start"], "处理中": ["assign", "complete"], "已完成": ["close"], "已标记误报": ["close"] }[a.status] || [];
  document.querySelector("[data-alarm-detail]").innerHTML = `
    <h3>${a.alarmType}</h3><div class="video">截图证据 + ${a.evidence.clipSeconds} 秒短视频</div>
    <div class="kv"><span>等级/状态</span><strong>${a.level} / ${a.status}</strong></div>
    <div class="kv"><span>置信度</span><strong>${Math.round(a.confidence * 100)}%</strong></div>
    <div class="field"><label>处置备注</label><textarea data-remark rows="3" placeholder="误报原因、指派说明或处置备注"></textarea></div>
    <div class="toolbar">${actions.map((x) => `<button class="${x === "markFalsePositive" ? "danger" : "primary"}" data-alarm-action="${x}">${actionLabel(x)}</button>`).join("")}</div>
    <div class="feed">${a.actions.map((act) => `<div class="feed-item"><strong>${actionLabel(act.action)}</strong><br><small>${act.createdAt} · ${act.remark || "无备注"}</small></div>`).join("") || "<p style='color:var(--muted)'>暂无处置记录</p>"}</div>`;
  document.querySelectorAll("[data-alarm-action]").forEach((btn) => btn.onclick = async () => {
    try {
      await api(`/api/projects/${state.currentProjectId}/alarms/${id}/actions`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: { action: btn.dataset.alarmAction, remark: document.querySelector("[data-remark]").value, assigneeUserId: "u_admin", assigneeDeptId: "security" },
      });
      toast("状态动作已写入 AlarmAction 和 AuditLog");
      renderAlarms();
    } catch (err) { toast(err.message); }
  });
}

function actionLabel(action) {
  return { confirm: "确认有效", markFalsePositive: "标记误报", assign: "指派", start: "开始处理", complete: "完成", close: "关闭" }[action] || action;
}

async function renderRules() {
  const data = await api(`/api/projects/${state.currentProjectId}/rules`);
  shell(`
    <section class="panel">
      <h3>新增规则</h3>
      <div class="rule-form">
        <input data-rule-name placeholder="规则名称" value="新增人员聚集规则">
        <input data-rule-type placeholder="规则类型" value="人员聚集">
        <input data-rule-event placeholder="事件类型" value="crowd">
        <input data-rule-provider placeholder="第三方来源" value="MegviiBox">
        <input data-rule-threshold type="number" min="0" max="1" step="0.01" value="0.85">
        <button class="primary" data-create-rule>新增规则</button>
      </div>
    </section>
    <table class="table"><thead><tr><th>规则</th><th>来源/事件</th><th>范围</th><th>阈值</th><th>命中/告警</th><th>误报率</th><th>操作</th></tr></thead><tbody>${data.rules.map((r) => `<tr><td><strong>${r.name}</strong><br><small>${r.ruleType} · ${r.enabled ? "启用" : "停用"}</small></td><td>${r.sourceProvider}<br><small>${r.eventType}</small></td><td>${r.targetScope} ${r.targetIdsJson.join(", ")}</td><td>${Math.round(r.threshold * 100)}%</td><td>${r.hitCount} / ${r.alarmCount}</td><td>${Math.round(r.falsePositiveRate * 1000) / 10}%</td><td><button class="ghost" data-toggle-rule="${r.id}" data-enabled="${r.enabled ? "0" : "1"}">${r.enabled ? "停用" : "启用"}</button> <button class="ghost" data-copy-rule="${r.id}">复制</button> <button class="danger" data-delete-rule="${r.id}">删除</button></td></tr>`).join("")}</tbody></table>`);
  document.querySelector("[data-create-rule]").onclick = async () => {
    await api(`/api/projects/${state.currentProjectId}/rules`, {
      method: "POST",
      body: {
        name: document.querySelector("[data-rule-name]").value,
        ruleType: document.querySelector("[data-rule-type]").value,
        eventType: document.querySelector("[data-rule-event]").value,
        sourceProvider: document.querySelector("[data-rule-provider]").value,
        threshold: Number(document.querySelector("[data-rule-threshold]").value || 0.85),
        targetScope: "project",
        targetIds: [state.currentProjectId],
      },
    });
    toast("规则已新增");
    renderRules();
  };
  document.querySelectorAll("[data-toggle-rule]").forEach((button) => {
    button.onclick = async () => {
      await api(`/api/projects/${state.currentProjectId}/rules/${button.dataset.toggleRule}/toggle`, { method: "POST", body: { enabled: button.dataset.enabled === "1" } });
      toast("规则状态已更新");
      renderRules();
    };
  });
  document.querySelectorAll("[data-copy-rule]").forEach((button) => {
    button.onclick = async () => {
      await api(`/api/projects/${state.currentProjectId}/rules/${button.dataset.copyRule}/copy`, { method: "POST", body: {} });
      toast("规则已复制");
      renderRules();
    };
  });
  document.querySelectorAll("[data-delete-rule]").forEach((button) => {
    button.onclick = async () => {
      await api(`/api/projects/${state.currentProjectId}/rules/${button.dataset.deleteRule}`, { method: "DELETE" });
      toast("规则已删除");
      renderRules();
    };
  });
}

async function renderAudit() {
  const data = await api(`/api/projects/${state.currentProjectId}/audit-logs`);
  shell(`<table class="table"><thead><tr><th>时间</th><th>动作</th><th>对象</th><th>结果</th></tr></thead><tbody>${data.auditLogs.map((a) => `<tr><td>${a.createdAt}</td><td>${a.action}</td><td>${a.objectType} / ${a.objectId || ""}</td><td>${a.result}</td></tr>`).join("")}</tbody></table>`);
}

function render() {
  if (!state.token || state.route === "login") return renderLogin();
  if (ADMIN_ROUTES.has(state.route) && !isProjectAdmin()) {
    state.route = "dashboard";
    toast("当前角色无权访问配置功能");
  }
  const routes = { dashboard: renderDashboard, cameras: renderCameras, map: renderMapConfig, alarms: renderAlarms, rules: renderRules, audit: renderAudit };
  routes[state.route]().catch((err) => { toast(err.message); if (err.message.includes("登录")) renderLogin(); });
}

bootstrap();
