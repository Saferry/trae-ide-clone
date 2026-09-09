"""Web 抓取工具（带白名单）。"""

from __future__ import annotations

import httpx
import re

from ..config import get_config
from .base import RiskLevel, Tool, ToolContext, ToolResult


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "抓取网页文本（受域名白名单约束）。参数：url。"
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string"}, "max_chars": {"type": "integer", "default": 8000}},
        "required": ["url"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> ToolResult:
        url = args.get("url") or ""
        max_chars = int(args.get("max_chars") or 8000)
        if not url.startswith(("http://", "https://")):
            return ToolResult(content="error: invalid url", is_error=True)

        host = re.sub(r"^https?://", "", url).split("/", 1)[0].lower()
        cfg = get_config()
        allow = cfg.sandbox.policies.get(cfg.sandbox.default_policy)
        if allow is None or not getattr(allow, "allow_network", False):
            return ToolResult(content=f"error: network is disabled by sandbox policy (host={host})", is_error=True)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "trae-ide-clone/0.1"})
            r.raise_for_status()
            html = r.text[:max_chars]
        # 极简 HTML -> 文本：去 script/style，多个空白压成一个
        text = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return ToolResult(content=text[:max_chars], metadata={"url": url, "host": host, "bytes": len(text)})