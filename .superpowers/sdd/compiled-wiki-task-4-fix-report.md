# Compiled Wiki Task 4 Fix — 相关实体区块

## 问题

Spec §5.2 要求主题页模板强制包含「相关实体 `[[entity-...]]`」区块，但 `wiki/compile.py` 的 `_render_topic_page` 仅有摘要、Chunks、Claims、相关原文、相关主题，缺少 `## 相关实体`。

## 变更

| 文件 | 说明 |
|------|------|
| `wiki/compile.py` | `_render_topic_page` 在「相关原文」与「相关主题」之间插入 `## 相关实体`，从 claims 的 subject/object 去重后输出 `entity_wikilink` |
| `wiki/compile.py` | `_required_links_for_cluster` 同时收集 claim.object 的 wikilink |
| `wiki/compile.py` | `_try_llm_merge` 校验 LLM 输出须含 `## 相关实体` |
| `wiki/prompts.py` | 规则 4 明确相关实体 wikilink 格式 |
| `tests/test_wiki_compile.py` | 断言模板页含相关实体及 subject/object 链接 |
| `tests/test_wiki_compile_llm.py` | 断言 prompt、LLM 成功路径与 fallback 模板均含相关实体 |

## 验证

```bash
python -m pytest tests/test_wiki_compile.py tests/test_wiki_compile_llm.py -q
# 5 passed
```

## 示例输出（模板路径）

```markdown
## 相关实体
- [[7天|7天]]
- [[退款|退款]]
```
