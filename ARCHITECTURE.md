# Trae IDE Clone —— 项目方案与技术架构

> 这是一份**借鉴 Trae IDE 设计理念、完全自主实现**的企业级 AI 编程助手平台方案。
> 区别于 Trae 闭源代码，本项目所有代码均为原创实现，可商用、可二次开发。

---

## 1. 项目目标

打造一个**可私有部署**的 AI 编程助手平台，让企业能够在自有网络环境中向研发团队交付：

- **类 Trae 的对话 + 智能体编程体验**：Chat、CUE 补全、Agent 全流程交付、Subagent 并行
- **企业级治理**：鉴权、限流、审计、可观测、模型路由
- **可扩展能力**：MCP 工具协议、自定义智能体、自定义模型
- **可集成底座**：VS Code / code-oss / JetBrains IDE

---

## 2. 产品形态（首版）

| 形态 | 内容 |
| --- | --- |
| **客户端** | VS Code 扩展（TypeScript），可装载到 VS Code、code-oss、VSCodium |
| **服务端** | Python FastAI（FastAPI + WebSocket），提供 REST + 流式 WS 双协议 |
| **协议** | 客户端/服务端通过自定义 JSON-over-WebSocket 协议交互（见 `shared/protocol/`） |
| **持久化** | SQLite（会话、日志）+ ChromaDB（代码索引向量） |
| **模型** | OpenAI 兼容协议（OpenAI、DeepSeek、Qwen、自建 vLLM 等）+ Anthropic 协议 |
| **部署** | Docker / docker-compose / Nginx 反向代理 |

---

## 3. 总体架构

```
┌──────────────────────────────────────────────────────────────┐
│                          客户端层                              │
│   VS Code / code-oss + trae-ide-clone 扩展 (TypeScript)      │
│   - Chat Webview   - Inline Completion   - Commands          │
└──────────────────────────────────────────────────────────────┘
                            │ WebSocket (流式) + REST (控制面)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                     AI 智能体服务端 (Python)                   │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ Main Agent │ │ Subagents    │ │ Tool Router  │            │
│  └────────────┘ └──────────────┘ └──────────────┘            │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ Code Index │ │ Rules Loader │ │ MCP Client   │            │
│  └────────────┘ └──────────────┘ └──────────────┘            │
│  ┌────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ Model Gate │ │ Auth/Quota   │ │ Audit Logger │            │
│  └────────────┘ └──────────────┘ └──────────────┘            │
└──────────────────────────────────────────────────────────────┘
                            │ HTTPS (OpenAI / Anthropic 协议)
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                       模型提供商                              │
│    OpenAI · Anthropic · DeepSeek · Qwen · 自建 vLLM · ...    │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. 模块清单（按模块）

### 4.1 客户端（`client/`）

| 模块 | 职责 |
| --- | --- |
| `extension.ts` | 扩展入口、命令注册、生命周期 |
| `chat/panel.ts` | Chat Webview 面板、会话管理、消息渲染 |
| `completion/provider.ts` | 行内补全（CUE）Provider |
| `agent/client.ts` | 与服务端 WS 客户端、流式事件处理 |
| `api/client.ts` | REST 客户端（创建会话、获取历史等） |
| `rules/loader.ts` | 工作区 `.trae/rules` 加载与拼装 |
| `config/config.ts` | 配置读写（服务端 URL、模型、Key 等） |

### 4.2 服务端（`server/src/trae_server/`）

| 子模块 | 职责 |
| --- | --- |
| `api/` | REST + WebSocket 路由 |
| `agents/` | 主智能体、子智能体、规划与执行循环 |
| `tools/` | 工具注册中心（文件、Bash、检索、网络、代码库） |
| `models/` | 模型适配层（OpenAI、Anthropic、Router） |
| `index/` | 代码库索引（Embedder + Chroma） |
| `mcp/` | MCP 客户端（stdio / SSE） |
| `rules/` | Rules 加载与解析 |
| `auth/` | API Key 鉴权、限流、配额 |
| `storage/` | SQLite 会话、消息、审计 |
| `config.py` | 配置中心（YAML / 环境变量） |
| `logging.py` | 结构化日志 |

### 4.3 共享协议（`shared/protocol/`）

| 文件 | 用途 |
| --- | --- |
| `events.ts` | WebSocket 事件类型（`agent.message` / `tool.call` / `tool.result` ...） |
| `messages.ts` | REST API 请求/响应结构 |

### 4.4 配置与部署（`config/` `deploy/`）

| 文件 | 用途 |
| --- | --- |
| `trae.example.yaml` | 服务端主配置 |
| `sandbox.example.json` | 沙箱策略 |
| `.trae/rules.example.md` | 项目规则示例 |
| `docker-compose.yml` | 一键启动 server + vector store |
| `server/Dockerfile` | 服务端镜像 |
| `nginx/nginx.conf` | 反向代理 + TLS 终止 |

---

## 5. 智能体核心设计

### 5.1 主智能体循环（ReAct + Plan 混合）

```
while not done:
    1. 收集上下文（#引用 + 规则 + 历史）
    2. 调用 LLM（流式输出）
    3. 解析输出：
        - <tool_call name=...>...</tool_call>  -> 调用工具
        - <plan>...</plan>                     -> 渲染计划并要求用户确认（高风险时）
        - 普通文本                            -> 流式回显
    4. 工具执行结果回填到上下文
    5. 终止条件：<final_answer> 或 LLM 主动结束
```

### 5.2 子智能体

通过 Markdown 声明（`.trae/agents/*.md`）：

```markdown
---
name: code-reviewer
description: 审查代码变更并指出问题
tools:
  - read_file
  - search_code
  - codebase_query
context_window: 8000
model: anthropic/claude-sonnet
---
你是严格的代码审查员，关注：
1. 安全漏洞
3. 性能瓶颈
4. 可维护性
```

主智能体在需要时通过 `delegate(subagent=...)` 工具派发，每个子智能体**独立上下文**。

### 5.3 工具系统

工具 = `(name, schema, risk_level, handler, sandbox_policy)`：

| 工具 | 风险 | 沙箱 |
| --- | --- | --- |
| `read_file` | 低 | 允许 |
| `write_file` | 中 | 受限目录 |
| `edit_file` | 中 | 受限目录 |
| `bash` | 高 | sandbox-exec / Bubblewrap |
| `search_code` | 低 | 允许 |
| `codebase_query` | 低 | 允许 |
| `web_fetch` | 中 | 域名白名单 |
| `delegate` | 中 | 由子智能体执行 |

---

## 6. 数据流（Chat 为例）

```
User ──► Extension Chat Webview
          │  send({session_id, content, refs:[...]})
        ▼
Extension WS Client ──► Server WS /ws/chat
                          │
                          ▼
                    AgentRunner.run()
                          │
                          ├──► Rules Loader (.trae/rules)
                          ├──► Codebase Indexer (#引用展开)
                          ├──► LLM.stream()
                          │       ▼
                          │    <tool_call name="bash">
                          │       └──► Sandbox.exec()
                          │             └──► result 回填
                          │
                          ├──► (可选) Subagent.delegate()
                          │
                          └──► stream events ──► Extension ──► Webview
```

---

## 7. 安全模型

| 维度 | 措施 |
| --- | --- |
| 客户端 ↔ 服务端 | API Key + 可选 JWT；TLS |
| 服务端 ↔ 模型 | 服务端持有模型 Key，客户端不感知 |
| Bash 执行 | 三平台沙箱（macOS sandbox-exec / Windows Job 对象 / Linux Bubblewrap + userns） |
| 文件写入 | 受限工作区目录 |
| 网络外联 | 域名白名单 + 速率限制 |
| 审计 | SQLite `audit_log` 表（who/when/action/payload） |
| 限流 | 滑动窗口限流（按 API Key / 按 IP） |

---

## 8. 首版交付清单（验收点）

- [ ] 项目结构与文档完整
- [ ] 服务端 `uvicorn trae_server.main:app` 可启动并通过 `/health` 自检
- [ ] REST API：`POST /v1/chat`、`POST /v1/agent/run`、`GET /v1/models`
- [ ] WebSocket `/ws/chat` 支持流式事件
- [ ] Agent 主循环可执行至少 3 个内置工具（read_file / write_file / bash）
- [ ] Subagent 可通过 Markdown 文件声明并被主智能体调用
- [ ] ChromaDB 代码库索引可构建与查询
- [ ] `.trae/rules` 加载生效
- [ ] MCP 客户端可连接 stdio MCP server
- [ ] 至少 1 个模型适配器（OpenAI 协议）端到端打通
- [ ] VS Code 扩展 `npm run compile` 通过
- [ ] Docker Compose 可一键起服务
- [ ] 单元测试通过（pytest）
- [ ] README / ARCHITECTURE / docs/* 齐备

---

## 9. 后续路线（非首版）

- 真实 VS Code fork（替换品牌、植入客户端 bundle）
- Web 端（TraeWork 形态）
- 团队级 Audit 面板
- 私有模型微调 Pipeline
- 端到端测试 + CI
- WebContainer / 远程沙箱

---

## 10. 风险与权衡

| 风险 | 应对 |
| --- | --- |
| LLM 输出不可控 | 流式中断、确认门、Plan 审核、dry_run |
| 沙箱逃逸 | 默认拒绝写白名单外路径；高风险命令拦截 |
| 大仓库索引性能 | JIT 触发 + 手动全量；分语言 embedding |
| 客户端体验 | 以扩展为主，IDE 整体改造留待 V2 |
| 模型成本 | Router 自动选便宜模型（启发式）；配额 |