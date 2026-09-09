# .trae 工作区级规则与子智能体定义

```
.trae/
├── rules.md          # 工作区主规则（注入每次对话）
├── agents/           # 子智能体定义（Markdown frontmatter + body）
│   ├── code-reviewer.md
│   ├── test-writer.md
│   └── docs-writer.md
└── context/          # 可选：项目背景文档
```

本目录是 Trae IDE Clone 服务端在工作区根目录下自动读取的配置文件。
服务端会：
1. 把 `rules.md` 拼接到系统消息
2. 把 `agents/*.md` 注册为可被 `delegate(subagent=name)` 调用的子智能体