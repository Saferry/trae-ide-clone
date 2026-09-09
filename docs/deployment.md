# 部署指南

支持三种部署形态：本地直接运行、Docker Compose、生产 K8s。

## 1. 本地直接运行

```bash
# 1. 启动服务端
cd server
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../config/trae.example.yaml ./trae.yaml
# 编辑 trae.yaml，填入模型 API Key

uvicorn trae_server.main:app --host 0.0.0.0 --port 8080 --reload
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
```

## 2. Docker Compose（一键起）

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY 等

docker compose up -d
```

默认暴露 8080（API）与 8443（HTTPS via Nginx）。HTTPS 证书自行准备并放入 `deploy/nginx/certs/`。

## 3. 生产部署（K8s）

`deploy/k8s/` 提供参考 manifests（待首版后补齐），要点：

1. 把 `config/trae.yaml` 做成 ConfigMap；API Key 用 Secret
2. 持久卷挂载 `/app/data`（SQLite + ChromaDB 索引）
3. 用 `Deployment` + `Service`（ClusterIP）
4. 通过 Ingress 暴露 HTTPS，配置 3600s 长连接用于 WS
5. HPA：根据 CPU + 并发会话数伸缩
6. 镜像仓库：自建 Harbor / ECR / GHCR

## 4. 客户端

### 4.1 直接安装到 VS Code / code-oss

```bash
cd client
npm install
npm run compile
npx vsce package
# 生成 trae-ide-clone-0.1.0.vsix
code --install-extension trae-ide-clone-0.1.0.vsix
```

或者直接把项目以扩展形式加载（开发模式）：
1. VS Code 打开项目，按 `F5` 启动 Extension Development Host

### 4.2 配置

打开 VS Code 设置 → 搜索 `Trae`：

| 选项 | 默认 | 说明 |
| --- | --- | --- |
| `trae.server.url` | `http://127.0.0.1:8080` | 服务端地址 |
| `trae.server.apiKey` | `""` | 服务端 API Key |
| `trae.server.wsPath` | `/v1/chat/ws` | WS 路径 |
| `trae.model.provider` | `openai-default` | 默认 provider |
| `trae.model.name` | `""` | 模型名（空则用 provider 默认） |
| `trae.completion.enabled` | true | 是否启用行内补全 |
| `trae.rules.autoLoad` | true | 自动加载工作区 `.trae/rules.md` |
| `trae.rules.path` | `.trae/rules.md` | 规则文件路径 |

## 5. 反向代理与 TLS

参考 `deploy/nginx/nginx.conf`。要点：

- 启用 WebSocket 透传（Upgrade / Connection 头 + 长 timeout）
- TLS 1.2+
- 建议在前置网关加 IP / API Key 限流

## 6. 升级

1. 停止旧版本（保留 `/app/data`）
2. 拉取新镜像 / 升级代码
3. 启动新版本（自动建表，向后兼容旧 schema）
4. 验证 `/health`

## 7. 故障排查

| 症状 | 检查 |
| --- | --- |
| 客户端显示 offline | 服务端 `/health`；服务端日志；网络；API Key |
| 模型调用失败 | `OPENAI_API_KEY` 是否设置；`/v1/models` 是否列出该 provider；`trae-server` 日志中的 4xx/5xx |
| 行内补全无响应 | `trae.completion.enabled`；服务端 `/v1/completion` 返回值；模型流式是否被打断 |
| 索引慢 | `indexer.ignore_patterns` 是否过滤了大目录；`max_file_size_kb` |
| 沙箱拦截 | `agent.dangerous_command_patterns` 与 `sandbox.example.json` 中 dangerous_commands |