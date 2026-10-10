# prompt-vault-mcp · 提示词库 MCP

**让 AI 直接说：「找到了，你的『周报生成』模板是……我帮你把工作记录填进去了。」**

零依赖 · 单文件 · stdio MCP 服务器 · 与 prompt-vault 共用数据 · 中文

---

## 它让 AI 能做什么

> 「我有哪些提示词模板？」
> → AI 调用 `list_prompts`，列出全部

> 「把那个周报模板填好，工作记录是……」
> → AI 调用 `render_prompt`，填充变量后直接给出可用提示词

> 「这个提示词不错，存下来叫『合同审查』，标签放法律」
> → AI 调用 `save_prompt` 入库

> 「有没有跟翻译相关的？」
> → AI 调用 `list_prompts` 带关键词搜索

---

## 提供的工具

| 工具 | 作用 |
|---|---|
| `list_prompts` | 列出/搜索（按标题、内容、标签） |
| `get_prompt` | 取模板完整内容 |
| `render_prompt` | 填充 `{{变量}}` 后输出 |
| `save_prompt` | 保存新提示词（首次会自动导入 5 个内置模板） |
| `list_tags` | 标签统计 |
| `stats` | 库统计与最常用排行 |

---

## 安装

```json
{
  "mcpServers": {
    "prompt-vault-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dafeiai918/prompt-vault-mcp", "prompt-vault-mcp"]
    }
  }
}
```

或本地文件（零依赖，Python 3.9+）：

```json
{
  "mcpServers": {
    "prompt-vault-mcp": {
      "command": "python",
      "args": ["/绝对路径/prompt-vault-mcp/prompt_vault_mcp.py"]
    }
  }
}
```

---

## 与其他项目共用数据

数据文件：`~/.prompt-vault/vault.json`

和命令行版 [prompt-vault](https://github.com/dafeiai918/prompt-vault) **共用同一份数据**：

- 命令行里 `add` 的提示词，MCP 里立刻能搜到
- AI 通过 MCP `save_prompt` 存的，命令行 `list` 也能看到

已有模板不用重新导入。

---

## 变量语法

用 `{{变量名}}` 占位：

```
请把下面的内容翻译成 {{目标语言}}，语气 {{语气}}：

{{内容}}
```

AI 会问你缺哪些变量，或从上下文自动填。

**未填的变量保持原样输出**（不会报错），并在末尾提示缺了哪些。

---

## 典型用法

| 场景 | 对 AI 说 |
|---|---|
| 复用模板 | 「用我的翻译模板，内容是 xxx」 |
| 存新模板 | 「把这段整理成模板存起来，叫 xxx」 |
| 找模板 | 「我之前存过一个改错别字的模板」 |
| 看统计 | 「我最常用哪些提示词」 |

---

## 相关项目

| 项目 | 用途 |
|---|---|
| [prompt-vault](https://github.com/dafeiai918/prompt-vault) | 同款命令行版（一键复制到剪贴板） |
| [llm-config-mcp](https://github.com/dafeiai918/llm-config-mcp) | 客户端配置生成 MCP |
| [relay-mcp](https://github.com/dafeiai918/relay-mcp) | 中转站账户管理 MCP |
| [awesome-relay](https://github.com/dafeiai918/awesome-relay) | 中转站与客户端精选导航 |

---

## License

MIT
