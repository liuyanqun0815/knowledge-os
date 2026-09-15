# AKOS Wiki Index 路由检索 — 设计规格

**日期**: 2026-09-15  
**状态**: 已确认  
**依赖**:
- 现有：`retrieval/wiki_index.py`（`WikiPageRetrieval`）、`orchestrator/nodes.py` retrieve 支路、`infra/bootstrap.py`、编译后 `index_wiki_root`
- 合成侧：wiki hits 仅作结构/上下文，事实仍以 claim/chunk 为准（既有约定不变）

**原则**:
1. **Index 只做路由**：`index.md` 永不进入答案证据 / Hit 正文上下文  
2. **只用关键词**：匹配与打分不直接使用整句 query  
3. **有种子才扩链**：1-hop 仅跟「能解析到真实 wiki `.md`」的链接  
4. **直接替换**：重写 `WikiPageRetrieval.search`，不保留伪 BM25/字符哈希，不做回退开关  
5. **按需读盘**：不缓存页正文；`index_wiki_root` 只记录 `wiki_root`

---

## 1. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| D1 | 关键词抽取 | jieba + 停用词/正则（无 jieba 则降级切分） |
| D2 | Index 命中 | 仅用命中种子；**不做**全库兜底 |
| D3 | Index 未命中 | 进程内遍历全部 wiki `.md` 打分；**不**扩链；**不**用外部 grep |
| D4 | 扩链 | 仅当有种子时 1-hop；只保留 `wiki_root/{target}.md` 存在的链接；忽略 `source-`/`chunk-` 与实体空链 |
| D5 | 打分 | 标题/路径 ×2 + 正文 ×1，候选集内归一化到 \[0,1\]；丢弃 0 分；top **5** |
| D6 | LLM fallback | 打分结果为空时，用问题 + 完整 `index.md` 选页；输出 `{"paths":[...]}`，条数 ≤ top_k（默认 5） |
| D7 | 接入 | 直接替换 `search`；bootstrap 注入可选 `llm_client` |
| D8 | 存储 | 纯按需读盘，无页正文内存索引 |

---

## 2. 动机

当前 `WikiPageRetrieval` 对编译 wiki 做「词法重叠 + 64 维字符哈希」检索，语义弱且与 `index.md` 目录结构脱节。本 KB（约 19 篇叶子 + 分 hub 的 `index.md`）标题/摘要已足够支撑关键词路由；页内大量 `[[实体短语]]` 并非真实文件（实测约 2000+ 空链 vs ~120 条真实页链，且真实链集中在「相关主题」），盲目跟链会引入噪声。

目标：以 **index 路由 + 受限 1-hop + 统一加权打分 + LLM 兜底选页** 替换旧检索，提升 Ask 三路融合中 wiki 支路的命中质量，且保持 `Hit` 端口与调用方不变。

---

## 3. 端到端流水线

```text
question
  → extract_keywords
  → 读盘解析 index.md → 关键词命中条目 → seeds[]
  → if seeds:
        读种子正文 → 抽 wikilink → 仅保留真实 .md → candidates = seeds ∪ neighbors
     else:
        rglob 全部叶子 .md（排除 index.md / log.md / .meta）→ candidates（不扩链）
  → 对 candidates 加权打分 → 归一化 → 按 score 降序取 top_k（默认 5，且 wiki 支路最多 5）
  → if 无正分结果:
        LLM(question, index.md) → {"paths": [...]} → 校验存在 → 读盘成 Hit（不再扩链/打分）
  → return list[Hit]
```

### 3.1 关键词

- 输入：仅 `question`
- 输出：去重后的 `keywords: list[str]`
- 模块：`retrieval/wiki_keywords.py` 的 `extract_keywords`
- 后续 index 匹配、正文打分、全扫 **一律**只用 keywords

### 3.2 Index 解析与种子

- 按需读取 `{wiki_root}/index.md`
- 解析条目形如：`- [[hub/leaf|标题]] — 摘要…`，以及 `### hub` / `>` 说明（hub 元数据可选，用于调试）
- 条目字段：`path`（无 `.md`）、`title`、`blurb`
- 种子条件：`path + title + blurb` 上关键词命中数 > 0
- **有种子则禁止全库扫描兜底**

### 3.3 1-hop（仅种子路径）

对每个种子页读盘，解析 `[[target|label]]` / `[[target]]`：

- 跳过 `target` 以 `source-` / `chunk-` 开头
- 仅当 `(wiki_root / f"{target}.md").is_file()` 为真时纳入邻居
- 不解析、不跟随不存在的实体链；不需要强制只扫「相关主题」小节（存在性过滤与当前语料等价且更稳）

### 3.4 未命中全扫

- `wiki_root.rglob("*.md")`
- 排除：路径含 `.meta`；文件名为 `index.md` / `log.md`
- **不**做 1-hop
- 与命中路径共用同一打分函数

### 3.5 打分

对每个候选（读盘得到 title、path、body）：

```text
raw = 2 * count(keywords, path + title) + 1 * count(keywords, body)
score = raw / max(raw over candidates)   # max==0 → 全部视为 0 分
```

- `count`：实现选定一种并全文一致（推荐：对每个 keyword 做子串命中计 1，或分词后集合交集大小；**禁止**混用两套）
- 丢弃 `score == 0`；排序取 `top_k`
- Wiki 支路 **最多返回 5** 条（`top_k = min(请求 top_k, 5)`，默认 5）

### 3.6 LLM fallback

**触发**：打分后无任何正分 Hit（含无候选）。

**输入**：用户问题 + 完整 `index.md` 文本（仅路由）。

**输出**（严格 JSON）：

```json
{"paths": ["政策/发票政策", "规则/优惠券使用规则"]}
```

约束：

- `len(paths) <= top_k`（≤5）
- path 为相对 wiki 根、无 `.md` 后缀
- 不存在或越界的 path **丢弃**
- LLM 未配置 / 调用失败 / JSON 解析失败 → 返回 `[]`，不抛给 Ask 主路径
- 校验通过的 path **直接读盘成 Hit**（可给固定 score 如 1.0 递减），**不再**扩链或关键词重打分

### 3.7 Hit 形态

与现有 `retrieval.ports.Hit` 对齐：

- `hit_type="wiki"`
- `ref_id`：相对 path（无 `.md`）或既有 page_id 约定（与 path 一致即可）
- `title`、`path`、`snippet`（摘要节或正文节选）、`score`

---

## 4. 模块与替换点

| 路径 | 职责 |
|------|------|
| `retrieval/wiki_keywords.py` | `extract_keywords` |
| `retrieval/wiki_index.py` | 重写 `WikiPageRetrieval`；删除伪 BM25/哈希索引结构 |
| `infra/bootstrap.py` | 构造时传入 `llm_client`（可与 Ask 共用） |
| `orchestrator/nodes.py` | 调用方式不变：`search(question, top_k=...)`；结果条数受 wiki 上限 5 约束 |

### 4.1 类接口

```python
class WikiPageRetrieval:
    def __init__(self, llm_client=None) -> None: ...
    def index_wiki_root(self, root: str | Path) -> None:
        """只保存 wiki_root；不缓存正文或向量。"""
    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        """见 §3 流水线。"""
```

编译完成 / admin 重编译后仍调用 `index_wiki_root`（语义：切换或确认根目录）。

### 4.2 明确不做

- Wiki 向量化 / embedding 索引  
- 外部 grep/rg 子进程  
- 多跳扩展  
- `index.md` 作为合成证据  
- 跟随实体 / `source-` / `chunk-` 链接  
- 旧哈希检索 feature flag  

---

## 5. 错误与降级

| 情况 | 行为 |
|------|------|
| `wiki_root` 未设置或不是目录 | `[]` |
| 无 `index.md` | 视为无种子 → 全扫；全扫也空则 LLM（若无 index 文本则跳过 LLM） |
| 单页读盘失败 | 跳过该页 |
| 关键词为空 | 无种子 → 全扫得分多为 0 → 走 LLM 或 `[]` |
| LLM 不可用 | fallback 跳过，返回 `[]` |

---

## 6. 测试

改写 / 扩展 `tests/test_wiki_retrieval.py`（必要时拆 `test_wiki_keywords.py`）：

1. **Index 命中**：关键词命中条目 → 种子 path 正确；hits 不含 `index.md`  
2. **1-hop 过滤**：正文/相关实体中的空链不进候选；真实 `hub/leaf.md` 邻居可进候选并参与打分  
3. **无种子全扫**：不扩链；标题命中分高于仅正文弱命中（在构造 fixture 上断言排序）  
4. **LLM fallback**：mock `llm_client` 返回 `{"paths":["政策/发票政策"]}` → Hit 路径正确；非法 path 丢弃  
5. **无 LLM / 坏 JSON**：`search` 返回 `[]`，不抛  
6. **top_k 上限**：请求 8 时 wiki 仍最多 5  

---

## 7. 实现备注（对本语料）

以 `data/kb/70958048-…/wiki` 为参照：约 19 叶子页；`index.md` 摘要完整，关键词路由预期主路径；1-hop 依赖存在性过滤即可避开 ~2000 条伪链。纯按需读盘在此规模下可接受。
