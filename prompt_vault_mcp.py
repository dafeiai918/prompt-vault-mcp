#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt-vault-mcp · 提示词库 MCP
让 AI 直接搜索、取用、保存你的提示词模板，并填充变量
零依赖 stdio MCP 服务器（与 prompt-vault 共用同一份数据）
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

__version__ = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

VAULT_PATH = Path.home() / ".prompt-vault" / "vault.json"
VAR_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


# ================= MCP 内核 =================

class MCPServer:
    def __init__(self, name: str, version: str, tools: list):
        self.name, self.version, self.tools = name, version, tools

    def _send(self, msg: dict) -> None:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _result(self, id_, result) -> None:
        self._send({"jsonrpc": "2.0", "id": id_, "result": result})

    def _error(self, id_, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})

    def handle(self, msg: dict) -> None:
        if not isinstance(msg, dict):
            return
        method, id_ = msg.get("method"), msg.get("id")
        if method == "initialize":
            self._result(id_, {"protocolVersion": PROTOCOL_VERSION,
                               "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": self.name, "version": self.version}})
        elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            return
        elif method == "ping":
            self._result(id_, {})
        elif method == "tools/list":
            self._result(id_, {"tools": [
                {"name": t["name"], "description": t["description"],
                 "inputSchema": t.get("inputSchema") or {"type": "object", "properties": {}}}
                for t in self.tools]})
        elif method == "tools/call":
            params = msg.get("params") or {}
            tool = next((t for t in self.tools if t["name"] == params.get("name")), None)
            if tool is None:
                self._error(id_, -32602, f"未知工具: {params.get('name')}")
                return
            try:
                out = tool["handler"](params.get("arguments") or {})
                self._result(id_, {"content": [{"type": "text", "text": str(out)}], "isError": False})
            except Exception as exc:
                self._result(id_, {"content": [{"type": "text",
                                                "text": f"错误: {type(exc).__name__}: {exc}"}],
                                   "isError": True})
        elif id_ is not None:
            self._error(id_, -32601, f"不支持的方法: {method}")

    def serve(self) -> None:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            for item in (msg if isinstance(msg, list) else [msg]):
                self.handle(item)


# ================= 数据层 =================

BUILTIN = [
    ("翻译成英文", "把下面的内容翻译成地道的英文，保持专业语气，只输出译文：\n\n{{内容}}", ["翻译"]),
    ("中文润色", "请润色下面这段中文，使其更通顺、更专业，不改变原意，只输出润色后的文本：\n\n{{内容}}", ["写作"]),
    ("长文总结", "请把下面的内容总结成 {{要点数}} 个要点，每条不超过 30 字：\n\n{{内容}}", ["总结"]),
    ("周报生成", "根据下面的工作记录生成周报，结构：本周完成 / 遇到的问题 / 下周计划：\n\n{{工作记录}}", ["职场"]),
    ("代码解释", "逐行解释下面的 {{语言}} 代码，指出潜在问题，用中文回答：\n\n```\n{{代码}}\n```", ["编程"]),
]


def empty_vault() -> dict:
    return {"version": 1, "next_id": 1, "prompts": []}


def load_vault() -> dict:
    if VAULT_PATH.exists():
        try:
            data = json.loads(VAULT_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("prompts"), list):
                data.setdefault("next_id", len(data["prompts"]) + 1)
                return data
        except Exception:
            pass
    return empty_vault()


def save_vault(vault: dict) -> None:
    VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VAULT_PATH.write_text(json.dumps(vault, ensure_ascii=False, indent=2), encoding="utf-8")


def find_prompt(vault: dict, key: str) -> dict | None:
    key = (key or "").strip()
    for item in vault["prompts"]:
        if item["id"] == key:
            return item
    low = key.lower()
    if not low:
        return None
    for item in vault["prompts"]:
        if low == item["title"].lower():
            return item
    for item in vault["prompts"]:
        if low in item["title"].lower():
            return item
    return None


def variables_of(content: str) -> list[str]:
    seen, out = set(), []
    for name in VAR_RE.findall(content):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def do_render(content: str, values: dict) -> str:
    def repl(match):
        name = match.group(1).strip()
        return values.get(name, match.group(0))
    return VAR_RE.sub(repl, content)


# ================= 工具 =================

def tool_list_prompts(args: dict) -> str:
    vault = load_vault()
    items = vault["prompts"]
    if not items:
        return ("提示词库是空的。可以用 save_prompt 保存第一条，"
                "或运行 prompt-vault init 导入内置模板。")
    keyword = (args.get("keyword") or "").strip().lower()
    tag = (args.get("tag") or "").strip()
    if keyword:
        items = [p for p in items if keyword in p["title"].lower()
                 or keyword in p["content"].lower()
                 or any(keyword in t.lower() for t in p["tags"])]
    if tag:
        items = [p for p in items if tag in p["tags"]]
    if not items:
        return "没有匹配的提示词。"
    lines = [f"共 {len(items)} 条：", ""]
    for p in items:
        vars_ = variables_of(p["content"])
        var_text = f"  变量: {', '.join(vars_)}" if vars_ else ""
        tag_text = f"  [{','.join(p['tags'])}]" if p["tags"] else ""
        lines.append(f"- {p['id']}  {p['title']}{tag_text}{var_text}")
    return "\n".join(lines)


def tool_get_prompt(args: dict) -> str:
    vault = load_vault()
    key = args.get("id") or args.get("title") or ""
    item = find_prompt(vault, key)
    if not item:
        return f"没找到「{key}」。用 list_prompts 看看有哪些。"
    vars_ = variables_of(item["content"])
    lines = [f"【{item['id']}】{item['title']}"]
    if vars_:
        lines.append(f"需要变量：{', '.join(vars_)}")
    lines += ["", item["content"]]
    return "\n".join(lines)


def tool_render_prompt(args: dict) -> str:
    vault = load_vault()
    key = args.get("id") or args.get("title") or ""
    item = find_prompt(vault, key)
    if not item:
        return f"没找到「{key}」。用 list_prompts 看看有哪些。"
    values = args.get("values") or {}
    if not isinstance(values, dict):
        return "values 需要是对象，如 {\"内容\": \"要翻译的文字\"}"
    missing = [v for v in variables_of(item["content"]) if v not in values]
    text = do_render(item["content"], values)
    lines = [text]
    if missing:
        lines += ["", f"（未填变量：{', '.join(missing)}，已保持原样）"]
    item["used"] = item.get("used", 0) + 1
    save_vault(vault)
    return "\n".join(lines)


def tool_save_prompt(args: dict) -> str:
    title = (args.get("title") or "").strip()
    content = args.get("content")
    if not title or not isinstance(content, str) or not content.strip():
        return "需要 title 和 content。"
    vault = load_vault()
    if not vault["prompts"]:
        for name, body, tags in BUILTIN:
            vault["prompts"].append({"id": f"p{vault['next_id']:03d}", "title": name,
                                     "content": body, "tags": tags,
                                     "created": time.time(), "used": 0})
            vault["next_id"] += 1
    if find_prompt(vault, title) and any(p["title"] == title for p in vault["prompts"]):
        return f"已存在同名提示词「{title}」，换个标题或用 get_prompt 查看。"
    tags = args.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    item = {"id": f"p{vault['next_id']:03d}", "title": title, "content": content,
            "tags": [str(t) for t in tags], "created": time.time(), "used": 0}
    vault["prompts"].append(item)
    vault["next_id"] += 1
    save_vault(vault)
    vars_ = variables_of(content)
    tail = f"\n检测到变量：{', '.join(vars_)}" if vars_ else ""
    return f"已保存 {item['id']}  {title}{tail}"


def tool_tags(args: dict) -> str:
    vault = load_vault()
    counter: dict[str, int] = {}
    for p in vault["prompts"]:
        for tag in p["tags"]:
            counter[tag] = counter.get(tag, 0) + 1
    if not counter:
        return "还没有标签。"
    lines = ["标签统计：", ""]
    for tag, count in sorted(counter.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {tag}  ({count})")
    return "\n".join(lines)


def tool_stats(args: dict) -> str:
    vault = load_vault()
    total = len(vault["prompts"])
    used = sum(p.get("used", 0) for p in vault["prompts"])
    top = sorted(vault["prompts"], key=lambda p: -p.get("used", 0))[:5]
    lines = [f"提示词库：{total} 条，累计使用 {used} 次", ""]
    if total and used:
        lines.append("最常用：")
        for p in top:
            if p.get("used"):
                lines.append(f"- {p['title']}  ({p['used']} 次)")
    lines.append(f"\n数据文件：{VAULT_PATH}")
    return "\n".join(lines)


TOOLS = [
    {"name": "list_prompts",
     "description": "列出或搜索提示词模板。用户问「我有哪些提示词」「有没有翻译的模板」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "keyword": {"type": "string", "description": "按标题/内容/标签搜索"},
         "tag": {"type": "string", "description": "按标签过滤"}}},
     "handler": tool_list_prompts},
    {"name": "get_prompt",
     "description": "取出某个提示词的完整内容。用户说「把那个周报模板给我」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string", "description": "ID 或标题关键词"}},
         "required": ["id"]},
     "handler": tool_get_prompt},
    {"name": "render_prompt",
     "description": "填充变量后输出可直接使用的提示词。用户说「用周报模板，工作记录是……」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string"},
         "values": {"type": "object", "description": "变量名到值的映射"}},
         "required": ["id"]},
     "handler": tool_render_prompt},
    {"name": "save_prompt",
     "description": "把一段好用的提示词存进库里。用户说「这个提示词存下来」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string"},
         "content": {"type": "string", "description": "用 {{变量名}} 表示占位符"},
         "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["title", "content"]},
     "handler": tool_save_prompt},
    {"name": "list_tags",
     "description": "列出所有标签及数量。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": tool_tags},
    {"name": "stats",
     "description": "提示词库统计：总数、使用次数、最常用。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": tool_stats},
]


def main() -> int:
    if os.name == "nt":
        try:
            sys.stdin.reconfigure(encoding="utf-8")
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    MCPServer("prompt-vault-mcp", __version__, TOOLS).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
