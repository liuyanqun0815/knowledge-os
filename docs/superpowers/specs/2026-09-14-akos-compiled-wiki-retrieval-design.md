# AKOS 编译 Wiki 层 + 三路检索融合 — 设计规格

**日期**: 2026-09-14  
**状态**: 已确认  
**依赖**:
- `docs/superpowers/specs/2026-09-09-akos-chunk-dual-index-synthesis-wiki-design.md`（Claim+Chunk 双索引 / synthesis）
- `docs/superpowers/specs/2026-09-11-akos-topic-cluster-design.md`（TopicCluster / topic 页导出）
- 现有：`wiki/export.py`、`retrieval/hybrid.py`、`retrieval/fusion.py`、`compiler/chunk_enrichment.py`

**原则**:
1. **同一知识库内的编译层** — 原始 Source 保留；Wiki 页是可增量更新的整理层，不是第二套 KB  
2. **Claim 管硬事实，原文 Chunk 管覆盖与证据，Wiki 主题页管综述入口** — 三路互补  
3. **LLM 只整理与组织，不捏造** — Wiki 更新必须可回溯到 Source/Claim/Chunk；synthesis 必须带引用  
4. **过期即删除** — stale chunk 不再长期堆砌；编译层以「当前生效」为准  

---

## 1. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| D1 | Wiki 落点 | **同库编译层**：`{AKOS_DATA_ROOT}/kb/{kb_id}/wiki/` 持久化并增量更新 |
| D2 | 检索形态 | **A 三路融合**：Claim + Wiki 主题页 + 原文 Chunk |
| D3 | 链接形态 | Obsidian 风格 `[[page\|label]]`（与现有 `wiki/export.py` 一致） |
| D4 | 原始文件 | **保留**；Wiki 不替代 Source，只整理与关联 |
| D5 | stale chunk | **硬删除**（`save_chunks` 后 purge；可选管理 API 一键清理历史脏数据） |

---

## 2. 动机

### 2.1 问题

| 问题 | 根因 |
|------|------|
| Chunk 面板「生效 4 / 过期 16」 | `save_chunks` 先 mark stale 再 upsert；少出来的 index 行永不删除 |
| Wiki 像快照不是知识库 | `export_wiki` 只读生成，上传后不持续改写主题页 |
| 检索碎片化 | 只有 Claim+碎 Chunk；缺少「整理好的主题入口」 |

### 2.2 目标

| # | 能力 | 成功标准 |
|---|------|----------|
| G1 | stale chunk 清理 | 重切分后该 source 下无 stale 行；UI 只显示生效段 |
| G2 | 编译 Wiki 增量更新 | 上传/enrich 后相关 `topic-*.md` 被合并更新，并写 `[[wikilink]]` |
| G3 | 三路检索 | Ask 可命中主题页；回答仍可引用 Claim 证据与原文 Chunk |
| G4 | 可降级 | `AKOS_WIKI_COMPILE=false` 时行为与现网一致（仅双路） |

---

## 3. 架构

```
上传 Source
  → ingest（Claim + active Chunk）
  → purge stale chunks          [P0]
  → enrich（topics/摘要）
  → topic cluster rebuild       [已有]
  → wiki compile (增量)         [新增]
       更新 topic-*.md / index.md / 关联 source|entity 链接

Ask
  → Claim 检索
  → Wiki 主题页检索             [新增]
  → 原文 Chunk 检索
  → RRF 三路融合
  → synthesis（绑定三类引用）
```

### 3.1 目录约定

```
{data_root}/kb/{kb_id}/wiki/
  index.md
  topic-{name}.md
  entity-{name}.md          # 可选：一期可仍由全量 export 生成，二期增量
  source-{id}.md            # 可选：源摘要页，链到 topics
  .meta/
    pages.json              # page_id → path, content_hash, updated_at, source_ids
    link_graph.json         # 可选：解析出的 [[link]] 邻接，供扩展检索
```

> 与「导出到任意目录」的 `export_wiki(output_dir=...)` 并存：  
> - **编译层**：固定 KB wiki 根，增量更新  
> - **导出**：仍可拷贝/再生成到用户指定目录（可从编译层同步或全量重建）

---

## 4. 过期 Chunk 硬删（P0）

### 4.1 行为

在 `KnowledgePort.save_chunks(source_id, chunks)` 成功写入新 active 后：

1. `DELETE`（或 memory `pop`）该 `source_id` 下 `status='stale'` 的全部 chunk  
2. 同步删除对应 `embeddings`（`ref_type='chunk'`）  
3. `chunk_retrieval.remove` 已按 source 重建索引时无需额外处理；若原地 purge，需保证索引不含已删 id

### 4.2 历史数据

提供一次性或管理接口：

- `POST /admin/knowledge-bases/{kb_id}/chunks/purge-stale`  
- 或启动时可选 `AKOS_PURGE_STALE_CHUNKS_ON_BOOT=false`（默认关）

### 4.3 UI

`SourceChunksPanel`：默认只拉 `status=active`；汇总不再强调「过期 N」（或过期恒为 0）。

---

## 5. 编译 Wiki 增量更新（P1）

### 5.1 触发时机

| 触发 | 动作 |
|------|------|
| `enrich_chunks` 结束（且 `AKOS_WIKI_COMPILE=true`） | 对本 source 涉及的 topics 做增量 compile |
| Topic cluster rebuild 后 | 确保 topic 页存在；可选刷新摘要 |
| 手动 | `POST .../wiki/compile`（全量或按 source） |
| 删 source | 从相关 topic 页移除该 source 链接；若主题无剩余源则标记或删除空页 |

### 5.2 增量算法（主题页）

对每个受影响 `topic_name`：

1. 收集：**该主题下 active chunks**（`topics`/`section_path`/TopicCluster 成员）+ **相关 active claims** + **source 列表**  
2. 读取已有 `topic-*.md`（若无则创建骨架）  
3. LLM 输入：旧页正文 + 本次新增/变更的 chunk 摘要与 claims + 规则「只合并，不编造；保留 wikilink」  
4. 写出新正文，强制包含区块：  
   - 摘要  
   - 要点（可含 Claim 列表）  
   - 相关原文 `[[source-...]]`  
   - 相关实体 `[[entity-...]]`  
   - 相关主题 `[[topic-...]]`  
5. 更新 `.meta/pages.json` 的 `content_hash`、`source_ids`、`updated_at`

无 LLM 或 `AKOS_WIKI_COMPILE_LLM=false` 时：用确定性模板合并（类似现 `export` 的 topic 页），仍写 link。

### 5.3 与 TopicCluster 关系

- **TopicCluster** 继续做图/成员集合的权威来源  
- **topic-*.md** 是面向人与检索的叙述层  
- 簇名规范化沿用 `normalize_topic_name`；一簇一页

### 5.4 非目标（一期不做）

- 把多篇原文物理合并成单个新 Source 文件入库  
- 单独第二个「Wiki 知识库」  
- 前端所见即所得 Wiki 编辑器  

---

## 6. 三路检索融合（P1/P2）

### 6.1 索引

| 通道 | 语料 | 实现要点 |
|------|------|----------|
| Claim | active claims | 现有 `HybridRetrieval` |
| Chunk | active source chunks | 现有 `ChunkRetrieval` |
| Wiki | 编译层 `topic-*.md`（及可选 entity 页） | 新增 `WikiPageRetrieval`：按页切段或整页 BM25/hash；meta 存 page_id、title、path |

### 6.2 融合

扩展 `fuse_hits` 为三路 RRF（或加权）：

```python
fused = rrf_fuse(
    claim_hits,
    wiki_hits,
    chunk_hits,
    weights=(claim_w, wiki_w, chunk_w),  # 默认如 1.0, 0.9, 0.8
)
```

默认权重可通过 settings：

- `AKOS_RETRIEVAL_CLAIM_WEIGHT=1.0`
- `AKOS_RETRIEVAL_WIKI_WEIGHT=0.9`
- `AKOS_RETRIEVAL_CHUNK_WEIGHT=0.8`

### 6.3 Link 扩展（P2，可开关）

若 top wiki hit 为 topic 页：

1. 解析该页 `[[wikilink]]`  
2. 额外纳入 1-hop 关联 source chunk / entity 摘要（限 top-M，防爆炸）  
3. `AKOS_WIKI_LINK_EXPAND=true` 时启用

### 6.4 Synthesis 约束

- 输入结构增加 `wiki_pages: [{title, excerpt, path, links}]`  
- 系统提示明确：**数字与规则以 Claim/原文为准；Wiki 仅作结构与综述**  
- 引用类型：`claim` | `chunk` | `wiki`

### 6.5 降级

| 条件 | 行为 |
|------|------|
| `AKOS_WIKI_COMPILE=false` | 无 wiki 索引；双路如旧 |
| wiki 目录空 | wiki_hits=[]，融合退化为双路 |
| LLM 不可用 | 模板 compile + 仍可检索 wiki 页 |

---

## 7. 配置开关

| 变量 | 默认 | 说明 |
|------|------|------|
| `AKOS_WIKI_COMPILE` | `true` | 启用同库编译层增量更新 |
| `AKOS_WIKI_COMPILE_LLM` | `true` | 主题页用 LLM 合并；false 则模板 |
| `AKOS_PURGE_STALE_CHUNKS` | `true` | save_chunks 后删除 stale |
| `AKOS_RETRIEVAL_WIKI_WEIGHT` | `0.9` | 三路中 wiki 权重 |
| `AKOS_WIKI_LINK_EXPAND` | `false` | 一期默认关，二期开 |

---

## 8. API / CLI（一期）

| 接口 | 作用 |
|------|------|
| `POST /admin/knowledge-bases/{kb_id}/wiki/compile` | 全量或 `?source_id=` 增量编译 |
| `POST /admin/knowledge-bases/{kb_id}/chunks/purge-stale` | 清理历史 stale |
| 现有 wiki export | 可从编译层复制或全量重建到指定目录 |

---

## 9. 实施分期

| 阶段 | 范围 |
|------|------|
| **P0** | `PURGE_STALE_CHUNKS` + 测试 + UI 默认只看 active |
| **P1** | 编译层目录 + 模板/LLM 增量 topic 页 + meta + Wiki 索引 + 三路融合 |
| **P2** | link 扩展、entity/source 页增量、compile API、导出与编译层同步策略 |

---

## 10. 验收标准

1. 重切分同一文档后，`list_chunks(status=all)` 无 stale；面板不再大量「已过期」  
2. 上传两篇同主题文档后，`wiki/topic-*.md` 存在且含两侧 `[[source-...]]`  
3. Ask 在仅靠碎 chunk 较弱时，能命中主题页并给出更完整流程类回答，同时仍有 Claim/Chunk 引用  
4. 关闭 `AKOS_WIKI_COMPILE` 后 Ask 行为与关闭前双路一致  

---

## 11. 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 合并改写引入错误 | 强制引用区块；synthesis 以 Claim/原文为准；可关 `WIKI_COMPILE_LLM` |
| 主题页膨胀 | 按 topic 增量；限制每次送入 LLM 的 chunk 数 |
| 三路噪声 | 可调权重；wiki 仅 index topic 页一期 |
| 与全量 export 冲突 | 明确编译层路径 vs 导出路径；export 可选 `--from-compile` |

---

## 12. 非目标

- 独立第二个 Wiki 知识库  
- 前端可视化 Wiki 编辑  
- Louvain / embedding 聚类替换现有 TopicCluster  
- 删除原始 Source（编译层不替代原文）  
