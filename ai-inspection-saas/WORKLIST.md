# AI 视频巡检 SaaS MVP 工作拆解

## 1. 需求与架构理解

- MVP 主链路：登录与多项目权限上下文 -> 摄像头/设备资产 -> 楼层地图与设备点位 -> 第三方 AI 事件接入 -> 平台规则过滤与告警生成 -> 指挥中心实时展示 -> 告警确认、指派、处置、证据和审计。
- 当前 PRD 明确第一版不做自研视觉模型、完整视频平台、工单系统、集团驾驶舱和移动端 App。
- 原型是静态 HTML + localStorage 演示，交互覆盖登录、大屏、摄像头、点位配置和告警查询，但没有真实 API、权限隔离、状态机或审计落库。

## 2. 当前环境结论

- macOS 12.1。
- Python 3.11.7、pip 23.3.1、SQLite 3.41.2、Git 可用。
- Codex 内置 Node v24.14.0 可用，但 npm/pnpm/yarn/corepack 不在 PATH。
- Docker 不可用。
- 第一版采用 Python 标准库 + SQLite + 原生 Web，避免联网安装依赖；后续可按模块边界迁移到 NestJS/Next.js/PostgreSQL。

## 3. 研发任务列表

### P0 基础底座

- 建立模块化单体目录：`auth`、`project`、`device`、`map`、`media`、`ai-adapter`、`rule`、`alarm`、`audit`。
- 建立 SQLite Schema 与种子数据。
- 实现登录、token 会话、项目列表、项目偏好。
- 所有项目级接口校验 `tenantId + projectId + role`。
- 写操作记录 `AuditLog`。

### P0 业务闭环

- 摄像头列表 API：状态、媒体状态、AI 能力、点位配置状态、楼层/区域由 `DevicePoint` 反查。
- 点位配置 API：按楼层查询、拖拽保存、相对坐标校验、楼层图版本校验、设备项目唯一点位约束。
- 指挥中心 API：项目 summary、楼层、点位、告警概览。
- 媒体播放会话 API：创建/释放短时 `MediaPlaySession`，前端不返回原始流地址。
- 告警 API：列表、详情、状态动作 `confirm / markFalsePositive / assign / start / complete / close`。
- 告警状态机校验、误报原因校验、动作幂等和审计。

### P1 接入与规则

- 平台规则列表与基础启停数据。
- 第三方 AI webhook：签名、nonce、幂等键、SourceEvent 标准化。
- 规则匹配：阈值、targetScope、excludeDeviceIds、冷却去重。
- 生成告警并记录首条 AlarmAction。

### P1 前端工程化

- 从静态原型迁移为 API 驱动页面。
- 登录后保存 token/currentProjectId。
- 项目切换统一清理媒体会话、页面筛选和缓存。
- 摄像头页支持筛选、详情抽屉、预览会话。
- 点位页支持拖拽保存、删除和楼层切换。
- 告警页支持筛选、详情、状态动作。

### P2 验证与扩展

- 添加冒烟测试脚本覆盖登录、项目隔离、点位保存、媒体会话、告警状态机。
- 添加 SSE 实时订阅。
- 添加证据下载令牌、附件、导出任务和审计查询页面。
- 添加地图上传与 SVG 清洗/PDF 异步转换。
