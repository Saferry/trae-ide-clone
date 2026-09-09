# 工作区规则示例 —— 拷贝为 .trae/rules.md
# Trae / Trae IDE Clone 工作区级规则
# 这些规则会在每次对话中作为系统消息注入

## 项目约定

- 所有 API 必须包含 OpenAPI 文档注释
- 公共函数必须有单元测试覆盖
- 数据库 schema 变更必须生成迁移文件
- 提交信息遵循 Conventional Commits

## 编码风格

- TypeScript: 2 空格缩进，使用 ESLint 默认规则
- Python: 4 空格缩进，遵循 PEP 8，使用 ruff 格式化
- 行长度不超过 120

## 禁止行为

- 不要直接修改 .env、*.yaml、*.key 等敏感文件
- 不要执行未在白名单中的网络请求
- 不要在没有 dry_run 的情况下执行 rm、mv 等破坏性命令

## 工作流

- 任何文件修改前必须先用 read_file 读取当前内容
- 多个相关文件修改应一次 plan 中说明
- 完成后必须说明改动摘要并自检