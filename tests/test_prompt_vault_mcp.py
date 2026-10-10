# -*- coding: utf-8 -*-
"""prompt-vault-mcp 测试：协议 + 数据层，用临时 vault"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prompt_vault_mcp as pv  # noqa: E402


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.server = pv.MCPServer("t", "1.0", pv.TOOLS)
        self.server._send = lambda m: self.sent.append(m)

    def _call(self, method, **kw):
        msg = {"jsonrpc": "2.0", "id": 1, "method": method}
        if kw:
            msg["params"] = kw
        self.server.handle(msg)
        return self.sent[-1]

    def test_initialize(self):
        self.assertEqual(self._call("initialize")["result"]["serverInfo"]["name"], "t")

    def test_tools_list(self):
        names = [t["name"] for t in self._call("tools/list")["result"]["tools"]]
        self.assertEqual(sorted(names), ["get_prompt", "list_prompts", "list_tags",
                                         "render_prompt", "save_prompt", "stats"])

    def test_unknown_tool(self):
        self.assertEqual(self._call("tools/call", name="x", arguments={})["error"]["code"], -32602)

    def test_tool_error_iserror(self):
        out = self._call("tools/call", name="render_prompt", arguments={})
        self.assertFalse(out["result"]["isError"])  # 缺参返回文本提示，不抛异常


class VaultTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = pv.VAULT_PATH
        pv.VAULT_PATH = Path(self.tmp.name) / "vault.json"

    def tearDown(self):
        pv.VAULT_PATH = self._orig
        self.tmp.cleanup()

    def test_empty_vault_message(self):
        self.assertIn("空的", pv.tool_list_prompts({}))

    def test_variables_of(self):
        self.assertEqual(pv.variables_of("{{a}} 和 {{ b }} 还有 {{a}}"), ["a", "b"])

    def test_render_keeps_unknown(self):
        self.assertEqual(pv.do_render("{{a}}-{{b}}", {"a": "X"}), "X-{{b}}")

    def test_save_seeds_builtins_and_adds(self):
        text = pv.tool_save_prompt({"title": "我的模板", "content": "写 {{东西}}", "tags": ["测试"]})
        self.assertIn("已保存", text)
        self.assertIn("东西", text)
        vault = pv.load_vault()
        self.assertEqual(len(vault["prompts"]), len(pv.BUILTIN) + 1)

    def test_save_duplicate_title(self):
        pv.tool_save_prompt({"title": "重复", "content": "x"})
        self.assertIn("已存在同名", pv.tool_save_prompt({"title": "重复", "content": "y"}))

    def test_save_requires_fields(self):
        self.assertIn("需要", pv.tool_save_prompt({"title": "", "content": ""}))
        self.assertIn("需要", pv.tool_save_prompt({"title": "x", "content": ""}))

    def test_list_and_search(self):
        pv.tool_save_prompt({"title": "翻译助手", "content": "翻译 {{内容}}", "tags": ["翻译"]})
        self.assertIn("翻译助手", pv.tool_list_prompts({}))
        self.assertIn("翻译助手", pv.tool_list_prompts({"keyword": "翻译"}))
        self.assertIn("没有匹配", pv.tool_list_prompts({"keyword": "zzzz不存在"}))
        self.assertIn("翻译助手", pv.tool_list_prompts({"tag": "翻译"}))
        self.assertIn("没有匹配", pv.tool_list_prompts({"tag": "不存在"}))

    def test_get_prompt(self):
        pv.tool_save_prompt({"title": "周报", "content": "写周报\n{{记录}}"})
        text = pv.tool_get_prompt({"id": "周报"})
        self.assertIn("需要变量", text)
        self.assertIn("写周报", text)
        self.assertIn("没找到", pv.tool_get_prompt({"id": "不存在"}))

    def test_render_prompt(self):
        pv.tool_save_prompt({"title": "翻译", "content": "翻译成英文：{{内容}}"})
        text = pv.tool_render_prompt({"id": "翻译", "values": {"内容": "你好"}})
        self.assertIn("翻译成英文：你好", text)
        self.assertNotIn("{{", text)

    def test_render_missing_reports(self):
        pv.tool_save_prompt({"title": "双变量", "content": "{{a}} 和 {{b}}"})
        text = pv.tool_render_prompt({"id": "双变量", "values": {"a": "1"}})
        self.assertIn("未填变量", text)
        self.assertIn("b", text)

    def test_render_bad_values_type(self):
        pv.tool_save_prompt({"title": "T", "content": "{{a}}"})
        self.assertIn("values 需要是对象",
                      pv.tool_render_prompt({"id": "T", "values": ["错"]}))

    def test_used_counter_increments(self):
        pv.tool_save_prompt({"title": "计数", "content": "{{a}}"})
        pv.tool_render_prompt({"id": "计数", "values": {"a": "1"}})
        pv.tool_render_prompt({"id": "计数", "values": {"a": "2"}})
        self.assertIn("2 次", pv.tool_stats({}))

    def test_tags_and_stats(self):
        pv.tool_save_prompt({"title": "A", "content": "x", "tags": ["职场", "写作"]})
        self.assertIn("职场", pv.tool_tags({}))
        self.assertIn("提示词库", pv.tool_stats({}))

    def test_find_by_id(self):
        pv.tool_save_prompt({"title": "找ID", "content": "x"})
        vault = pv.load_vault()
        target = next(p for p in vault["prompts"] if p["title"] == "找ID")
        self.assertEqual(pv.find_prompt(vault, target["id"])["title"], "找ID")


if __name__ == "__main__":
    unittest.main(verbosity=2)
