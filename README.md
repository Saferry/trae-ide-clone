# Trae IDE Clone

> 借鉴 Trae IDE 设计、完全自研实现的**企业级 AI 编程助手平台**。

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.4%2B-blue)](https://www.typescriptlang.org)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

## 简介

Trae IDE Clone 是一套**可私有部署**的 AI 编程助手平台。客户端以 VS Code 扩展形态运行在
VS Code / code-oss / VSCodium 中，服务端是独立的 Python FastAPI 服务，对接 OpenAI 兼容的
任意模型（OpenAI、Anthropic、DeepSeek、Qwen、自建 vLLM 等），并支持 MCP 工具协议、Subagent
并行、子智能体自定义与代码库向量检索。

## 核心能力

- **Agent 主循环**：Plan → 用户确认 → 分步执行 → 验证 → 交付
- **Subagent**：Markdown 声明式子智能体，独立上下文，可并行
- **CUE 补全**：行内补全 + 链式预测 + 智能导入与重命名
- **代码库索引**：基于 ChromaDB 的语义检索 + `#` 显式引用
- **Rules**：`.trae/rules` 工作区级规则
- **MCP**：可连接任意 MCP server（stdio / SSE），注册为工具
- **多模型**：OpenAI 兼容协议 + Anthropic + 自定义
- **企业级**：API Key 鉴权、限流、审计日志、结构化日志
- **沙箱**：三平台命令隔离（macOS / Windows / Linux）

## 项目结构

```
trae-ide-clone/
├── client/           VS Code 扩展（TypeScript）
├── server/           AI 智能体服务端（Python FastAPI）
├── shared/           客户端 / 服务端共享协议
├── config/           配置示例（trae.yaml、sandbox.json、.trae/rules）
├── deploy/           Docker / Nginx
├── docs/             架构、API、部署、开发文档
└── docker-compose.yml
```

## 快速开始

### 1. 启动服务端

```bash
cd server
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../config/trae.example.yaml ./trae.yaml
# 编辑 trae.yaml 填入模型 API Key
uvicorn trae_server.main:app --host 0.0.0.0 --port 8080 --reload
```

健康检查：

```bash
curl http://localhost:8080/health
```

### 2. 安装客户端扩展

```bash
cd client
npm install
npm run compile
# 在 VS Code 中：Ctrl+Shift+P → "Extensions: Install from VSIX"
# 或使用 vsce 打包：vsce package
```

### 3. 一键 Docker 启动

```bash
cp config/trae.example.yaml trae.yaml
# 编辑 trae.yaml 填入模型 Key
docker compose up -d
```

## 文档导航

- [ARCHITECTURE.md](./ARCHITECTURE.md) —— 总体方案与技术架构
- [docs/architecture.md](./docs/architecture.md) —— 详细架构设计
- [docs/api.md](./docs/api.md) —— REST + WebSocket API 参考
- [docs/deployment.md](./docs/deployment.md) —— 部署指南
- [docs/development.md](./docs/development.md) —— 开发者指南
- [docs/acceptance.md](./docs/acceptance.md) —— 首版验收清单

## 适用场景

- 企业内部 AI 编程助手私有化
- 团队统一模型路由与配额管理
- 通过 MCP 接入企业内部工具链（Jira、GitLab、自研系统）
- 基于 `.trae/rules` 沉淀团队编码规范

## 安全声明

本项目**不包含**任何 Trae IDE / 字节跳动公司的闭源代码；VS Code 端以开源 code-oss
（MIT 协议）为运行底座，所有功能均自主实现，可商用、可二次开发。

## License

MIT