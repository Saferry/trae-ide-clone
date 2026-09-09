# 首版验收清单（v0.1.0）

> 用于团队内部确认首版是否达到"可演示、可使用、可演进"的状态。

## 1. 工程基础

- [ ] 项目目录完整，无占位文件
- [ ] `.gitignore` 覆盖敏感文件（.env、*.yaml、*.key、*.db）
- [ ] LICENSE 文件存在（MIT）
- [ ] README + ARCHITECTURE 完整
- [ ] GitHub Actions CI 配置存在（服务端 + 客户端）

## 2. 服务端（Python FastAPI）

- [ ] `uvicorn trae_server.main:app` 可启动
- [ ] `/health`、`/healthz`、`/` 返回 200
- [ ] `/v1/models` 需要 `X-API-Key`，校验后返回 providers 列表
- [ ] `/v1/chat` 接受完整消息并返回 answer（依赖真实模型 Key 才能 e2e 跑通）
- [ ] WebSocket `/v1/chat/ws` 支持流式事件（session / text / tool_call / tool_result / plan / done）
- [ ] 工具注册中心含 11 个内置工具：read_file / write_file / edit_file / list_dir / bash / grep / glob / codebase_query / index_build / web_fetch / delegate
- [ ] `bash` 工具拒绝高危命令（rm -rf / 等）
- [ ] `bash` 工具在 Linux 上走 bwrap（若可用），否则兜底执行 + timeout
- [ ] `.trae/rules.md` 解析并拼装到 system prompt
- [ ] `.trae/agents/*.md` 解析为子智能体并可被 `delegate()` 调用
- [ ] ChromaDB 可用时走向量检索；不可用时降级到 SQLite + cosine
- [ ] MCP server（stdio）可在配置后被工具注册中心收录
- [ ] 配置可通过 YAML 文件 + 环境变量插值
- [ ] 结构化日志（structlog / JSON）
- [ ] SQLite 持久化（Session / Message / AuditLog）
- [ ] API Key 鉴权 + 速率限制（滑动窗口）

## 3. 客户端（VS Code 扩展）

- [ ] `npm install && npm run compile` 通过
- [ ] 命令面板命令 `Trae: Open Chat` / `Run Agent on Selection` / `Toggle Inline Completion` / `Index Workspace` 注册成功
- [ ] Ctrl+Shift+T 打开 Chat Webview
- [ ] Chat Webview 与服务端 WS 连通后可流式显示文本 / 工具调用 / 计划
- [ ] 行内补全 Provider 在编辑器中触发（基于分隔符 + 停顿）
- [ ] 状态栏显示连接状态 + 模型名
- [ ] 配置通过 VS Code Settings 持久化（trae.server.* / trae.model.* / trae.completion.enabled / trae.rules.*）

## 4. 部署

- [ ] `docker-compose.yml` 一键启动服务端 + Nginx
- [ ] 服务端 Dockerfile 基于 python:3.11-slim，含 bwrap
- [ ] Nginx 反向代理支持 WebSocket Upgrade
- [ ] 数据持久化通过 docker volume（trae-data / trae-workspace）

## 5. 测试

- [ ] `pytest -q` 通过（基本模块、API、模型适配、Agent runner）
- [ ] 至少覆盖：config / rules / file tools / bash / api / model adapter

## 6. 文档

- [ ] README.md
- [ ] ARCHITECTURE.md
- [ ] docs/api.md
- [ ] docs/deployment.md
- [ ] docs/development.md
- [ ] docs/acceptance.md（本文件）

## 7. 上线 / 演示

- [ ] 在演示环境跑通以下剧本：
  1. 服务端启动 → `/health` 200
  2. 客户端装上 → StatusBar 显示 Trae 在线
  3. Chat 中问"列出工作区文件" → 模型调 `list_dir` → 渲染结果
  4. Chat 中问"在 foo.py 中实现 X" → 模型依次 `read_file` → `edit_file` → 验证
  5. Chat 中问"用 code-reviewer 审查刚才的改动" → 委派子智能体 → 返回审查 JSON
  6. 在编辑器中输入 → 行内补全触发

## 8. 已知限制（非首版阻塞）

- 无真实 VS Code fork（依赖用户安装 code-oss / VS Code 后加载扩展）
- 无 Web 版 / 移动版（仅 TraeWork 形态的未来版本）
- 无团队级审计面板（依赖 SQLite 自查）
- 无端到端 Playwright / Cypress 测试
- 无 Model Fine-tuning Pipeline

## 9. 验收签字

| 角色 | 姓名 | 日期 |
| --- | --- | --- |
| 产品 | | |
| 工程 | | |
| 安全 | | |
| 运维 | | |