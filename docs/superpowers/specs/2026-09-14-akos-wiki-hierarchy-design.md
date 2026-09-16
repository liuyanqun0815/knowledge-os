# AKOS 编译 Wiki 目录结构优化 — 设计规格（方案 A）

**日期**: 2026-09-14  
**状态**: 已确认  
**依赖**:
- `docs/superpowers/specs/2026-09-14-akos-compiled-wiki-retrieval-design.md`（同库编译层 + 三路检索）
- 现有：`wiki/compile.py`、`wiki/links.py`、`knowledge/topic_cluster.py`、`retrieval/wiki_index.py`

**原则**:
1. **像 llm-wiki / Obsidian**：文件名即标题，无 `topic-` 前缀；用目录表达层次  
2. **先减碎、再美化**：短语级标签并入父主题页，而不是只改文件名  
3. **可检索、可链接**：`[[wikilink]]` 与 Wiki 索引跟随新路径；旧 `topic-*` 页可迁移/清理  
4. **渐进**：一期规则归并 + 目录约定；可选 LLM 辅助选父主题  

---

## 1. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| D1 | 总体方案 | **A：去前缀 + 子目录 + 短语归并到父主题页** |
| D2 | 文件名 | 无 `topic-` 前缀；`sanitize(标题).md` |
| D3 | 目录 | `{wiki_root}/{领域枢纽}/子页.md`；枢纽用 `_index.md` |
| D4 | 平铺废弃 | 新编译不再写根目录 `topic-*.md` |

---

## 2. 动机

当前 `{data_root}/kb/{kb_id}/wiki/` 下大量 `topic-不知道.md`、`topic-不归我管.md` 等：

- 主题来自 chunk `topics` / 小节名，粒度偏「短语」而非「知识枢纽」  
- `topic_page_name` 强制 `topic-` 前缀且全部落在根目录  
- 「相关主题」列出几乎全部其它页，噪声大  

目标：更接近 llm-wiki 的可读目录树，同时减少无效独立页。

---

## 3. 目标目录结构

```text
{wiki_root}/
  index.md
  客服话术/
    _index.md              # 枢纽综述 + 子页 / 原文档链接
    开场.md
    沟通规范.md
    禁用表达.md            # 合并：不知道、不归我管、你找别人…
  投诉升级/
    _index.md
    一级在线客服.md
    二级客服主管.md
    …
  .meta/
    pages.json             # path 含相对子路径；kind=hub|topic
    hierarchy.json         # 可选：raw_topic → parent_hub / leaf_page
```

**命名规则**:
- 枢纽目录名 = 规范化后的父主题显示名（如 `客服话术`）  
- 子页文件名 = 叶子主题显示名，**无前缀**  
- wikilink：`[[客服话术/沟通规范|沟通规范]]` 或 Obsidian 风格仅标题 `[[沟通规范]]`（一期推荐**带路径**以避免重名）

---

## 4. 主题归并（减碎）

### 4.1 角色

| 角色 | 含义 | 落盘 |
|------|------|------|
| **Hub（枢纽）** | 领域级主题（客服话术、投诉升级、尺码选择） | `{Hub}/_index.md` |
| **Leaf（叶子）** | 可独立成页的子主题（开场、响应时效） | `{Hub}/{Leaf}.md` |
| **Snippet（短语）** | 不当独立页：禁语、口头禅、过短标签 | 并入某 Leaf 的「要点/禁用表达」小节，或 Hub `_index` |

### 4.2 归并策略（一期）

1. **别名 / 父映射表**（扩展 `DEFAULT_TOPIC_ALIASES` 或新 `TOPIC_PARENTS`）  
   - 例：`不知道|不归我管|你找别人|没办法|不可能` → parent `客服话术`，leaf `禁用表达`，mode=`snippet`  
   - 例：`客服开场|开场` → parent `客服话术`，leaf `开场`  
   - 例：`客服沟通|客服话术规范` → parent `客服话术`，leaf `沟通规范`  

2. **启发式**（无映射时）  
   - 名称长度 ≤ 4 且无「流程/规范/指南/升级」等枢纽词 → 倾向 snippet，挂到同 source 最常见 hub，否则 `未分类`  
   - 含「一级/二级/三级」→ hub=`投诉升级`，leaf=规范化职级名  
   - 否则：若能匹配已有 hub 前缀（如以「客服」开头）→ 该 hub 下 leaf；否则自建 hub=自身（单页 `_index.md` only）

3. **可选 LLM**（`AKOS_WIKI_HIERARCHY_LLM`，默认 false）  
   - 输入候选 topic 列表，输出 `{raw, parent, leaf, role: hub|leaf|snippet}` JSON  
   - 失败回退规则  

### 4.3 对 TopicCluster 的影响

- **聚类仍可按规范化名**；编译层再映射到 hub/leaf  
- 或：在 `build_topic_clusters` 后增加 `assign_wiki_hierarchy(clusters) -> HierarchyPlan`  
- Snippet 不单独写 md；其 claims/chunks 并入目标 leaf/hub 页  

### 4.4 「相关主题」

- 仅链：**同 hub 下其它 leaf** + **父 hub** + **显式相关 hub（可选 top-K）**  
- **禁止**再挂全库所有 topic  

---

## 5. 链接与索引变更

| 组件 | 变更 |
|------|------|
| `wiki/links.py` | `topic_page_path(hub, leaf=None) -> "客服话术/_index"` / `"客服话术/沟通规范"`；废弃默认 `topic-` 前缀 |
| `wiki/compile.py` | 按 hierarchy 写子目录；生成 `_index.md`；snippet 合并渲染 |
| `wiki/export.py` | 导出路径与 compile 对齐（或导出仍扁平但推荐与 compile 一致） |
| `retrieval/wiki_index.py` | 递归扫描 `**/*.md`（跳过 `.meta`）；`path` 存相对路径 |
| `.meta/pages.json` | `path` 含目录；增加 `hub`、`role` |

**迁移**：
- 启动或 `wiki/compile` 全量时：删除/归档根目录遗留 `topic-*.md`（`AKOS_WIKI_MIGRATE_FLAT=true` 默认 true）  
- 旧 wikilink `[[topic-客服沟通]]`：meta 可保留 `aliases` 重定向一季，或全量重编译后不再保证  

---

## 6. 配置

| 变量 | 默认 | 说明 |
|------|------|------|
| `AKOS_WIKI_HIERARCHY` | `true` | 启用目录 + 归并 |
| `AKOS_WIKI_HIERARCHY_LLM` | `false` | LLM 辅助选父主题 |
| `AKOS_WIKI_MIGRATE_FLAT` | `true` | 编译时清理旧 `topic-*.md` 平铺页 |
| `AKOS_WIKI_MAX_RELATED` | `12` | 相关主题上限（同 hub 优先） |

电商客服种子映射可放 `domains/ecommerce_cs/wiki_hierarchy.py`（或 YAML），其它域可扩展。

---

## 7. 验收

1. 编译后根目录无（或极少）`topic-*.md`；存在如 `客服话术/_index.md`、`客服话术/禁用表达.md`  
2. 「不知道」「不归我管」等**不再**独立成文件，内容出现在禁用表达/父页要点中  
3. `index.md` 按 hub 分组列出子页  
4. Ask / Wiki 检索仍能命中新路径页面  
5. `AKOS_WIKI_HIERARCHY=false` 时保持旧行为（平铺 + 前缀）以便回滚  

---

## 8. 非目标（一期）

- 完整 concepts/sources/entities 多树（方案 C）  
- 前端可视化 Wiki 编辑器  
- 自动从任意中文语料学习层次（无种子映射时仅启发式 + 可选 LLM）  

---

## 9. 实施分期

| 阶段 | 范围 |
|------|------|
| **P0** | links 去前缀 + 子目录路径 API；compile 写 `{hub}/{leaf}.md` + `_index.md`；相关主题限同 hub；迁移删平铺 |
| **P1** | ecommerce 种子 parent/snippet 映射 + 启发式；snippet 合并渲染 |
| **P2** | 可选 hierarchy LLM；export 对齐；重定向别名 |

---

## 10. 风险

| 风险 | 缓解 |
|------|------|
| 重名 leaf（不同 hub 下同名） | wikilink 带路径 |
| 映射不全仍碎 | 启发式 + 未分类 hub；可后续补映射 |
| 破坏已有书签/外链 | 全量重编译 + migrate 开关；文档说明 |
