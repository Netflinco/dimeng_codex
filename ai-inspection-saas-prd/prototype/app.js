const STORAGE_KEY = "ai_inspection_demo_points";

const devices = [
  { id: "CAM-L1-001", name: "L1 中庭北侧摄像头", type: "camera", floor: "L1", area: "中庭", status: "online", rules: ["人员聚集", "通道占用"] },
  { id: "CAM-L1-002", name: "L1 扶梯口摄像头", type: "camera", floor: "L1", area: "扶梯口", status: "alarm", rules: ["人员聚集"] },
  { id: "CAM-L1-003", name: "L1 消防通道摄像头", type: "camera", floor: "L1", area: "消防通道", status: "online", rules: ["通道占用", "烟火识别"] },
  { id: "CAM-L1-004", name: "L1 主入口摄像头", type: "camera", floor: "L1", area: "主入口", status: "online", rules: ["客流密度"] },
  { id: "CAM-L1-005", name: "L1 零售区东侧摄像头", type: "camera", floor: "L1", area: "零售区", status: "online", rules: ["异常徘徊"] },
  { id: "CAM-B1-021", name: "B1 停车场东区摄像头", type: "camera", floor: "B1", area: "停车场", status: "warn", rules: ["违停", "画面异常"] },
  { id: "CAM-B1-022", name: "B1 卸货区摄像头", type: "camera", floor: "B1", area: "卸货区", status: "online", rules: ["地面积水", "长时占用"] },
  { id: "SEN-B1-012", name: "B1 设备通道烟感", type: "sensor", floor: "B1", area: "设备通道", status: "online", rules: ["烟火联动"] },
  { id: "CAM-L3-031", name: "L3 餐饮区烟火摄像头", type: "camera", floor: "L3", area: "餐饮区", status: "online", rules: ["烟火识别"] },
  { id: "CAM-L3-032", name: "L3 扶梯厅摄像头", type: "camera", floor: "L3", area: "扶梯厅", status: "online", rules: ["人员聚集"] },
  { id: "SEN-L1-011", name: "L1 中庭烟感", type: "sensor", floor: "L1", area: "中庭", status: "online", rules: ["烟火联动"] },
  { id: "ACS-L1-006", name: "L1 设备间门禁", type: "access", floor: "L1", area: "设备间", status: "offline", rules: ["门禁异常"] }
];

const defaultPoints = [
  { deviceId: "CAM-L1-001", floor: "L1", xRatio: 0.34, yRatio: 0.36, rotation: 35, status: "online" },
  { deviceId: "CAM-L1-002", floor: "L1", xRatio: 0.55, yRatio: 0.32, rotation: 95, status: "alarm" },
  { deviceId: "CAM-L1-003", floor: "L1", xRatio: 0.72, yRatio: 0.57, rotation: 180, status: "online" },
  { deviceId: "CAM-L1-004", floor: "L1", xRatio: 0.18, yRatio: 0.45, rotation: 20, status: "online" },
  { deviceId: "CAM-L1-005", floor: "L1", xRatio: 0.82, yRatio: 0.38, rotation: 210, status: "online" },
  { deviceId: "SEN-L1-011", floor: "L1", xRatio: 0.48, yRatio: 0.46, rotation: 0, status: "online" },
  { deviceId: "CAM-B1-021", floor: "B1", xRatio: 0.28, yRatio: 0.48, rotation: 30, status: "warn" },
  { deviceId: "CAM-B1-022", floor: "B1", xRatio: 0.66, yRatio: 0.54, rotation: 150, status: "online" },
  { deviceId: "SEN-B1-012", floor: "B1", xRatio: 0.52, yRatio: 0.35, rotation: 0, status: "online" },
  { deviceId: "CAM-L3-031", floor: "L3", xRatio: 0.42, yRatio: 0.38, rotation: 80, status: "online" },
  { deviceId: "CAM-L3-032", floor: "L3", xRatio: 0.64, yRatio: 0.58, rotation: 210, status: "online" }
];

const floorConfigs = {
  L1: {
    title: "L1 楼层地图",
    subtitle: "主入口/中庭/零售区",
    labels: ["主入口", "中庭", "零售区", "消防通道", "扶梯连廊"],
    hint: "L1 一层 · 拖拽未配置摄像头到地图后生成楼层/区域"
  },
  B1: {
    title: "B1 停车场地图",
    subtitle: "停车区/卸货区/设备通道",
    labels: ["车行入口", "停车场东区", "停车场西区", "卸货区", "设备通道"],
    hint: "B1 停车场 · 拖拽未配置摄像头到停车区点位"
  },
  L2: {
    title: "L2 零售楼层地图",
    subtitle: "零售环廊/服务通道",
    labels: ["北侧零售", "中庭连廊", "南侧零售", "服务通道", "扶梯厅"],
    hint: "L2 暂无正式点位，可从全量摄像头列表拖拽配置"
  },
  L3: {
    title: "L3 餐饮楼层地图",
    subtitle: "餐饮区/扶梯厅/后厨通道",
    labels: ["餐饮入口", "餐饮中庭", "后厨通道", "消防通道", "扶梯厅"],
    hint: "L3 餐饮区 · 拖拽未配置摄像头到餐饮/扶梯区域"
  }
};

const alarms = [
  { id: "ALM-20260509-001", type: "人员聚集", level: "P2", status: "待确认", camera: "L1 扶梯口摄像头", floor: "L1", area: "扶梯口", confidence: "91%", time: "2026-05-09 10:24:31", sla: "剩余 08:42" },
  { id: "ALM-20260509-002", type: "消防通道占用", level: "P1", status: "已确认", camera: "L1 消防通道摄像头", floor: "L1", area: "消防通道", confidence: "94%", time: "2026-05-09 10:18:09", sla: "超时 02:10" },
  { id: "ALM-20260509-003", type: "画面异常", level: "P3", status: "处理中", camera: "B1 停车场东区摄像头", floor: "B1", area: "停车场", confidence: "86%", time: "2026-05-09 09:52:44", sla: "剩余 21:11" },
  { id: "ALM-20260509-004", type: "烟火识别", level: "P1", status: "已关闭", camera: "L3 餐饮区摄像头", floor: "L3", area: "餐饮区", confidence: "89%", time: "2026-05-09 09:21:16", sla: "已完成" },
  { id: "ALM-20260509-005", type: "异常徘徊", level: "P3", status: "待确认", camera: "L1 零售区东侧摄像头", floor: "L1", area: "零售区", confidence: "84%", time: "2026-05-09 08:48:03", sla: "剩余 26:18" },
  { id: "ALM-20260509-006", type: "客流密度过高", level: "P2", status: "已确认", camera: "L1 主入口摄像头", floor: "L1", area: "主入口", confidence: "88%", time: "2026-05-09 08:32:45", sla: "剩余 10:03" }
];

const mockFallbackAlarms = [
  { id: "MOCK-20260509-901", type: "垃圾堆放", level: "P3", status: "待确认", camera: "L2 服务通道摄像头", floor: "L2", area: "服务通道", confidence: "82%", time: "2026-05-09 11:08:20", sla: "剩余 28:00" },
  { id: "MOCK-20260509-902", type: "地面积水", level: "P2", status: "处理中", camera: "B1 卸货区摄像头", floor: "B1", area: "卸货区", confidence: "87%", time: "2026-05-09 10:56:12", sla: "剩余 12:40" },
  { id: "MOCK-20260509-903", type: "门禁异常", level: "P3", status: "已标记误报", camera: "L1 设备间门禁", floor: "L1", area: "设备间", confidence: "79%", time: "2026-05-09 10:41:02", sla: "已复核" }
];

function normalizeViewportScale() {
  const screenWidth = window.screen?.availWidth || window.innerWidth;
  const ratio = window.innerWidth / Math.max(screenWidth, 1);
  const likelyZoomedOut = ratio > 1.35 || window.devicePixelRatio < 0.9;
  document.documentElement.classList.toggle("zoomed-out", likelyZoomedOut);
}

function getPoints() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return [...defaultPoints];
  try {
    const parsed = JSON.parse(stored);
    if (parsed.some((point) => !point.floor)) {
      savePoints(defaultPoints);
      return [...defaultPoints];
    }
    return parsed.map((point) => {
      if (point.floor) return point;
      const device = deviceById(point.deviceId);
      return { ...point, floor: device?.floor || "L1" };
    });
  } catch {
    return [...defaultPoints];
  }
}

function savePoints(points) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(points));
}

function deviceById(id) {
  return devices.find((device) => device.id === id);
}

function statusLabel(status) {
  const map = { online: "在线", offline: "离线", alarm: "告警", warn: "异常" };
  return map[status] || status;
}

function pointIcon(device) {
  if (!device) return "?";
  if (device.type === "camera") return "CAM";
  if (device.type === "sensor") return "SEN";
  if (device.type === "access") return "ACS";
  return "DEV";
}

function getSelectedFloor() {
  return document.querySelector("[data-floor-select]")?.value || "L1";
}

function pointsForFloor(floor) {
  return getPoints().filter((point) => (point.floor || deviceById(point.deviceId)?.floor || "L1") === floor);
}

function pointForDevice(deviceId) {
  return getPoints().find((point) => point.deviceId === deviceId);
}

function configuredLocation(deviceId) {
  const point = pointForDevice(deviceId);
  if (!point) return { floor: "未配置", area: "未配置", label: "未配置" };
  const config = floorConfigs[point.floor] || floorConfigs.L1;
  const area = nearestZoneLabel(point, config);
  return { floor: point.floor, area, label: `${point.floor} / ${area}` };
}

function nearestZoneLabel(point, config) {
  const zoneByX = point.xRatio < 0.25 ? 0 : point.xRatio < 0.48 ? 1 : point.xRatio < 0.68 ? 4 : 2;
  const zoneIndex = point.yRatio > 0.54 ? 3 : zoneByX;
  return config.labels[zoneIndex] || "公共区";
}

function applyFloorMap(floor, root = document) {
  const config = floorConfigs[floor] || floorConfigs.L1;
  const maps = root.querySelectorAll("[data-config-map], [data-dashboard-map]");
  maps.forEach((map) => {
    Object.keys(floorConfigs).forEach((key) => map.classList.remove(`floor-${key.toLowerCase()}`));
    map.classList.add(`floor-${floor.toLowerCase()}`);
  });
  root.querySelector("[data-floor-title]") && (root.querySelector("[data-floor-title]").textContent = config.title);
  root.querySelector("[data-floor-subtitle]") && (root.querySelector("[data-floor-subtitle]").textContent = config.subtitle);
  root.querySelector("[data-map-hint]") && (root.querySelector("[data-map-hint]").textContent = config.hint);
  root.querySelectorAll("[data-zone-label]").forEach((label, index) => {
    label.textContent = config.labels[index] || "";
  });
}

function showToast(message) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 2200);
}

function initLogin() {
  const button = document.querySelector("[data-login]");
  if (!button) return;
  button.addEventListener("click", () => {
    button.textContent = "正在进入...";
    window.setTimeout(() => {
      window.location.href = "dashboard.html";
    }, 450);
  });
}

function renderPoints(container, options = {}) {
  if (!container) return;
  container.querySelectorAll(".point").forEach((point) => point.remove());
  const floor = options.floor || getSelectedFloor();
  const points = pointsForFloor(floor);

  points.forEach((point) => {
    const device = deviceById(point.deviceId);
    const node = document.createElement("div");
    node.className = `point ${point.status || device?.status || "online"}`;
    node.dataset.deviceId = point.deviceId;
    node.style.left = `${point.xRatio * 100}%`;
    node.style.top = `${point.yRatio * 100}%`;
    node.style.transform = `rotate(${point.rotation || 0}deg)`;
    node.textContent = pointIcon(device);
    node.title = device ? `${device.name} ${statusLabel(point.status || device.status)}` : point.deviceId;
    container.appendChild(node);

    if (options.draggable) {
      node.addEventListener("pointerdown", (event) => startPointDrag(event, node, container));
      node.addEventListener("click", () => selectPoint(point.deviceId));
    } else {
      node.addEventListener("click", () => showToast(`${device?.name || point.deviceId}：打开实时视频会话`));
    }
  });
}

function floorRelativePosition(event, container) {
  const rect = container.getBoundingClientRect();
  const xRatio = Math.min(0.98, Math.max(0.02, (event.clientX - rect.left) / rect.width));
  const yRatio = Math.min(0.98, Math.max(0.02, (event.clientY - rect.top) / rect.height));
  return { xRatio, yRatio };
}

function startPointDrag(event, node, container) {
  event.preventDefault();
  const deviceId = node.dataset.deviceId;
  const floor = getSelectedFloor();
  node.setPointerCapture(event.pointerId);
  node.classList.add("selected");

  const move = (moveEvent) => {
    const next = floorRelativePosition(moveEvent, container);
    node.style.left = `${next.xRatio * 100}%`;
    node.style.top = `${next.yRatio * 100}%`;
  };

  const up = (upEvent) => {
    const next = floorRelativePosition(upEvent, container);
    const points = getPoints().map((point) => (
      point.deviceId === deviceId && point.floor === floor ? { ...point, ...next, version: (point.version || 1) + 1 } : point
    ));
    savePoints(points);
    node.releasePointerCapture(upEvent.pointerId);
    node.removeEventListener("pointermove", move);
    node.removeEventListener("pointerup", up);
    selectPoint(deviceId);
  };

  node.addEventListener("pointermove", move);
  node.addEventListener("pointerup", up);
}

function selectPoint(deviceId) {
  document.querySelectorAll(".point").forEach((point) => {
    point.classList.toggle("selected", point.dataset.deviceId === deviceId);
  });
  const device = deviceById(deviceId);
  const floor = getSelectedFloor();
  const point = getPoints().find((item) => item.deviceId === deviceId && (item.floor || device?.floor) === floor);
  const panel = document.querySelector("[data-selected-device]");
  if (!panel || !device || !point) return;

  panel.innerHTML = `
    <h3>${device.name}</h3>
    <div class="kv"><span>设备编号</span><strong>${device.id}</strong></div>
    <div class="kv"><span>设备类型</span><strong>${device.type}</strong></div>
    <div class="kv"><span>配置位置</span><strong>${configuredLocation(device.id).label}</strong></div>
    <div class="kv"><span>运行状态</span><strong>${statusLabel(device.status)}</strong></div>
    <div class="kv"><span>xRatio</span><strong>${point.xRatio.toFixed(3)}</strong></div>
    <div class="kv"><span>yRatio</span><strong>${point.yRatio.toFixed(3)}</strong></div>
    <div class="field">
      <label>朝向角度</label>
      <input data-rotation-input type="number" value="${point.rotation || 0}" min="0" max="359">
    </div>
    <div class="toolbar">
      <button class="primary-btn" data-rotate-save>保存属性</button>
      <button class="danger-btn" data-remove-point>删除点位</button>
    </div>
  `;

  panel.querySelector("[data-rotate-save]").addEventListener("click", () => {
    const rotation = Number(panel.querySelector("[data-rotation-input]").value || 0);
    const points = getPoints().map((item) => (
      item.deviceId === deviceId && item.floor === floor ? { ...item, rotation, version: (item.version || 1) + 1 } : item
    ));
    savePoints(points);
    renderMapConfig();
    showToast("点位属性已保存，版本号已更新");
  });

  panel.querySelector("[data-remove-point]").addEventListener("click", () => {
    savePoints(getPoints().filter((item) => !(item.deviceId === deviceId && item.floor === floor)));
    renderMapConfig();
    showToast("点位已删除，设备回到未配置列表");
  });
}

function renderDeviceLists() {
  const unconfigured = document.querySelector("[data-unconfigured-list]");
  const configured = document.querySelector("[data-configured-list]");
  if (!unconfigured || !configured) return;
  const floor = getSelectedFloor();
  const pointIds = new Set(getPoints().map((point) => point.deviceId));

  const makeCard = (device, isConfigured) => {
    const card = document.createElement("div");
    card.className = `device-card ${isConfigured ? "configured" : ""}`;
    card.draggable = !isConfigured;
    card.dataset.deviceId = device.id;
    const location = configuredLocation(device.id);
    card.innerHTML = `
      <strong>${device.name}</strong>
      <small>${device.id} · ${isConfigured ? location.label : "未配置点位"}</small>
      <span class="status ${device.status}">${statusLabel(device.status)}</span>
    `;
    if (!isConfigured) {
      card.addEventListener("dragstart", (event) => {
        event.dataTransfer.setData("text/plain", device.id);
      });
    } else {
      card.addEventListener("click", () => selectPoint(device.id));
    }
    return card;
  };

  unconfigured.innerHTML = "";
  configured.innerHTML = "";

  devices.filter((device) => device.type === "camera").forEach((device) => {
    if (pointIds.has(device.id)) configured.appendChild(makeCard(device, true));
    else unconfigured.appendChild(makeCard(device, false));
  });

  if (!unconfigured.children.length) {
    unconfigured.innerHTML = `<div class="empty-mini">暂无未配置摄像头</div>`;
  }
  if (!configured.children.length) {
    configured.innerHTML = `<div class="empty-mini">暂无已配置摄像头</div>`;
  }
}

function renderMapConfig() {
  const map = document.querySelector("[data-config-map]");
  if (!map) return;
  const floor = getSelectedFloor();
  applyFloorMap(floor, document);
  renderDeviceLists();
  renderPoints(map, { draggable: true, floor });
}

function initMapConfig() {
  const map = document.querySelector("[data-config-map]");
  if (!map) return;
  renderMapConfig();

  map.addEventListener("dragover", (event) => event.preventDefault());
  map.addEventListener("drop", (event) => {
    event.preventDefault();
    const deviceId = event.dataTransfer.getData("text/plain");
    if (!deviceId) return;
    const floor = getSelectedFloor();
    if (pointsForFloor(floor).some((point) => point.deviceId === deviceId)) {
      showToast("该设备已在当前楼层配置点位，不能重复放置");
      return;
    }
    if (getPoints().some((point) => point.deviceId === deviceId && point.floor !== floor)) {
      showToast("该设备已配置在其他楼层，请先删除原点位后再重新配置");
      return;
    }
    const next = floorRelativePosition(event, map);
    const device = deviceById(deviceId);
    savePoints([...getPoints(), { deviceId, floor, ...next, rotation: 0, status: device?.status || "online", version: 1 }]);
    renderMapConfig();
    selectPoint(deviceId);
    showToast("设备已放置到地图，请保存当前楼层配置");
  });

  const saveBtn = document.querySelector("[data-save-map]");
  const resetBtn = document.querySelector("[data-reset-map]");
  const previewBtn = document.querySelector("[data-preview-map]");
  const conflictBtn = document.querySelector("[data-conflict-demo]");
  const floorSelect = document.querySelector("[data-floor-select]");

  saveBtn?.addEventListener("click", () => {
    showToast(`楼层 ${getSelectedFloor()} 点位已保存：floorMapVersion=3，采用乐观锁校验`);
  });

  resetBtn?.addEventListener("click", () => {
    const floor = getSelectedFloor();
    savePoints([...getPoints().filter((point) => point.floor !== floor), ...defaultPoints.filter((point) => point.floor === floor)]);
    renderMapConfig();
    showToast(`已恢复 ${floor} 示例点位`);
  });

  previewBtn?.addEventListener("click", () => {
    window.location.href = "dashboard.html";
  });

  conflictBtn?.addEventListener("click", () => {
    showToast("保存失败：楼层图版本已变更，请刷新后重新校准");
  });

  floorSelect?.addEventListener("change", () => {
    renderMapConfig();
    document.querySelector("[data-selected-device]").innerHTML = `
      <h3>点位属性</h3>
      <p style="color:var(--muted);line-height:1.7">已切换至 ${getSelectedFloor()}，左侧仍展示全量摄像头；拖拽未配置摄像头即可绑定到当前楼层。</p>
    `;
    showToast(`已切换至 ${getSelectedFloor()} 楼层地图`);
  });
}

function initDashboard() {
  const map = document.querySelector("[data-dashboard-map]");
  if (!map) return;
  let currentFloor = "L1";
  const renderDashboardFloor = (floor) => {
    currentFloor = floor;
    applyFloorMap(floor, document);
    renderPoints(map, { floor });
    document.querySelectorAll("[data-floor-tab]").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.floorTab === floor);
    });
  };
  renderDashboardFloor(currentFloor);
  document.querySelectorAll("[data-floor-tab]").forEach((tab) => {
    tab.addEventListener("click", () => renderDashboardFloor(tab.dataset.floorTab));
  });
  const clock = document.querySelector("[data-clock]");
  if (clock) {
    const tick = () => {
      const now = new Date();
      clock.textContent = now.toLocaleString("zh-CN", { hour12: false });
    };
    tick();
    setInterval(tick, 1000);
  }
}

function initCameras() {
  const body = document.querySelector("[data-camera-rows]");
  if (!body) return;
  const points = new Set(getPoints().map((point) => point.deviceId));
  body.innerHTML = devices.filter((device) => device.type === "camera").map((device) => `
    <tr data-camera-id="${device.id}">
      <td><strong>${device.name}</strong><br><small>${device.id}</small></td>
      <td>${configuredLocation(device.id).label}</td>
      <td><span class="status ${device.status}">${statusLabel(device.status)}</span></td>
      <td><span class="tag">${device.rules.join("</span> <span class=\"tag\">")}</span></td>
      <td>${points.has(device.id) ? "已配置" : "未配置"}</td>
      <td>
        <button class="ghost-btn" data-preview="${device.id}">预览</button>
        <button class="ghost-btn" data-locate="${device.id}">定位</button>
      </td>
    </tr>
  `).join("");

  body.querySelectorAll("[data-preview]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      selectCamera(button.dataset.preview);
    });
  });

  body.querySelectorAll("[data-locate]").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      window.location.href = `map-config.html?device=${button.dataset.locate}`;
    });
  });

  body.querySelectorAll("tr").forEach((row) => {
    row.addEventListener("click", () => selectCamera(row.dataset.cameraId));
  });

  selectCamera("CAM-L1-001");
}

function selectCamera(cameraId) {
  const device = deviceById(cameraId);
  const drawer = document.querySelector("[data-camera-drawer]");
  if (!device || !drawer) return;
  const hasPoint = getPoints().some((point) => point.deviceId === cameraId);
  const location = configuredLocation(cameraId);
  drawer.innerHTML = `
    <h3>${device.name}</h3>
    <div class="video-box">Media Gateway 播放会话 · ${statusLabel(device.status)}</div>
    <div class="kv"><span>设备编号</span><strong>${device.id}</strong></div>
    <div class="kv"><span>楼层区域</span><strong>${location.label}</strong></div>
    <div class="kv"><span>视频协议</span><strong>RTSP，经 Media Gateway 转 WebRTC</strong></div>
    <div class="kv"><span>边缘网关</span><strong>EDGE-MALL-01</strong></div>
    <div class="kv"><span>点位状态</span><strong>${hasPoint ? "已配置" : "未配置"}</strong></div>
    <div class="kv"><span>AI 规则</span><strong>${device.rules.join("、")}</strong></div>
    <div class="toolbar">
      <button class="primary-btn" onclick="location.href='map-config.html?device=${device.id}'">配置点位</button>
      <button class="ghost-btn" onclick="showToast('已请求短时鉴权播放地址')">获取预览</button>
    </div>
  `;
}

function initAlarms() {
  const body = document.querySelector("[data-alarm-rows]");
  const detail = document.querySelector("[data-alarm-detail]");
  if (!body || !detail) return;

  function renderRows(status = "all") {
    const filtered = status === "all" ? alarms : alarms.filter((alarm) => alarm.status === status);
    const rows = filtered.length ? filtered : mockFallbackAlarms;
    const note = filtered.length ? "" : `
      <tr>
        <td colspan="6">
          <div class="empty-state">
            <span class="mock-note">当前筛选无正式告警，以下展示虚拟样例数据</span>
            <strong>暂无匹配结果</strong>
            <p>产品原型保留 mock 告警，便于确认详情、证据和状态流转体验。</p>
          </div>
        </td>
      </tr>
    `;
    body.innerHTML = note + rows.map((alarm) => `
      <tr data-alarm-id="${alarm.id}">
        <td><strong>${alarm.id}</strong><br><small>${alarm.time}</small></td>
        <td>${alarm.type}</td>
        <td><span class="status ${alarm.level === "P1" ? "alarm" : alarm.level === "P2" ? "warn" : "online"}">${alarm.level}</span></td>
        <td>${alarm.camera}<br><small>${alarm.floor} / ${alarm.area}</small></td>
        <td>${alarm.confidence}</td>
        <td>${alarm.status}</td>
      </tr>
    `).join("");
    body.querySelectorAll("tr").forEach((row) => row.addEventListener("click", () => renderDetail(row.dataset.alarmId)));
    renderDetail(rows[0]?.id || alarms[0].id);
  }

  function renderDetail(alarmId) {
    const alarm = alarms.find((item) => item.id === alarmId) || mockFallbackAlarms.find((item) => item.id === alarmId) || alarms[0];
    detail.innerHTML = `
      <h3>${alarm.type}</h3>
      <div class="evidence">截图证据 + 10-30 秒短视频片段</div>
      <div class="kv"><span>告警编号</span><strong>${alarm.id}</strong></div>
      <div class="kv"><span>摄像头</span><strong>${alarm.camera}</strong></div>
      <div class="kv"><span>等级/状态</span><strong>${alarm.level} / ${alarm.status}</strong></div>
      <div class="kv"><span>置信度</span><strong>${alarm.confidence}</strong></div>
      <div class="kv"><span>SLA</span><strong>${alarm.sla}</strong></div>
      <div class="toolbar">
        <button class="primary-btn" data-action="confirm">确认有效</button>
        <button class="ghost-btn" data-action="dispatch">派单处理</button>
        <button class="danger-btn" data-action="false">标记误报</button>
      </div>
      <div class="timeline">
        <div>${alarm.time} AI 规则引擎生成告警</div>
        <div>10:25:02 大屏推送，中控待确认</div>
        <div>证据留存周期 30 天，下载需审计</div>
      </div>
    `;
    detail.querySelectorAll("[data-action]").forEach((button) => {
      button.addEventListener("click", () => {
        const text = button.dataset.action === "false" ? "已标记误报，原因：现场无异常" : "状态操作已写入 AlarmAction 和 AuditLog";
        showToast(text);
      });
    });
  }

  document.querySelector("[data-alarm-status]")?.addEventListener("change", (event) => {
    renderRows(event.target.value);
  });
  renderRows();
}

function initActiveNav() {
  const file = window.location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll(".nav a").forEach((link) => {
    const href = link.getAttribute("href");
    link.classList.toggle("active", href === file);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  normalizeViewportScale();
  window.addEventListener("resize", normalizeViewportScale);
  initActiveNav();
  initLogin();
  initDashboard();
  initMapConfig();
  initCameras();
  initAlarms();
});
