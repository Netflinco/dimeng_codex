# AI Inspection SaaS MVP

本仓库包含 AI 商业空间巡检 SaaS 的产品资料、可运行 MVP、前端页面和回归测试资料。

## 目录结构

- `ai-inspection-saas/`：可运行 MVP，包含 Python 后端、静态前端、示例数据种子和冒烟测试。
- `ai-inspection-saas-prd/`：PRD、技术架构文档和早期静态原型。

## 本地启动

运行环境只依赖 Python 3 标准库，无需安装第三方包。

```bash
cd ai-inspection-saas
python3 server.py 8090 --reset
```

启动后访问：

```text
http://127.0.0.1:8090
```

演示账号：

- 租户：`joycity-demo`
- 操作员：`operator01` / `123456`
- 项目管理员：`admin` / `123456`

`--reset` 会重新生成本地 SQLite 示例库；不加该参数则复用当前本地数据。

## 冒烟测试

服务启动后，在另一个终端执行：

```bash
cd ai-inspection-saas
python3 smoke_test.py
```

当前回归记录见 `ai-inspection-saas/QA_REGRESSION_TEST_REPORT_2026-05-11.md`。

## 发布说明

- `data.sqlite3` 是本地运行时数据库，会由 `server.py` 自动创建并灌入演示数据，不提交到 GitHub。
- `web/uploads/` 是运行时上传目录，不提交到 GitHub。
- 仓库适合先作为源代码和交付资料发布到 GitHub；若需要公网访问，还需要额外部署到云服务器、容器平台或 PaaS。
