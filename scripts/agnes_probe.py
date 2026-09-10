"""探测 Agnes API 连通性、列出可用模型并测试 chat/completion/embedding。"""

import asyncio
import json
from pathlib import Path

import httpx

AGNES_KEY = "sk-xFvFzcXBJeSv17KOGSp6bQIbVLoXNwceqVrUnmgXsa839vyT"
AGNES_BASE = "https://api.agnes-ai.cn/v1"


async def main():
    async with httpx.AsyncClient(base_url=AGNES_BASE, timeout=30, headers={"Authorization": f"Bearer {AGNES_KEY}"}) as c:
        # 1. 模型列表
        print("=== 1. 模型列表 ===")
        r = await c.get("/models")
        print(f"HTTP {r.status_code}")
        if r.status_code == 200:
            models = r.json()
            print(json.dumps(models, indent=2, ensure_ascii=False)[:1500])
        else:
            print(r.text[:500])

        # 2. 简单 chat
        print("\n=== 2. Chat 测试 ===")
        r = await c.post("/chat/completions", json={
            "model": "glm-5.3",
            "messages": [{"role": "user", "content": "只回答yes/no:你能正常响应吗?"}],
            "max_tokens": 8,
        })
        print(f"HTTP {r.status_code}")
        print(r.text[:500])

        # 3. Stream 测试
        print("\n=== 3. Stream 测试 ===")
        r = await c.post("/chat/completions", json={
            "model": "glm-5.3",
            "messages": [{"role": "user", "content": "说'hello'"}],
            "max_tokens": 20,
            "stream": True,
        })
        print(f"HTTP {r.status_code}")
        print(r.text[:300])


if __name__ == "__main__":
    asyncio.run(main())
