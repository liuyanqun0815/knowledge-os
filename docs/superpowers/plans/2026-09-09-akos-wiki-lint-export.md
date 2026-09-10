# AKOS Wiki Lint + Export（借鉴 LLM Wiki）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 Claim/PG 为权威存储的前提下，借鉴 [LLM Wiki](https://github.com/luotwo/llm-wiki/blob/master/README.md) 的 **Lint（健康检查）** 与 **Wiki 视图层（只读导出）**，并增强上传后的「复利反馈」摘要。

**Architecture:** 新增纯函数模块 `knowledge/lint.py` 与 `wiki/export.py`，通过现有 `KnowledgePort` / `GraphPort` / `EvidencePort` 扫描；暴露 `akos lint` / `akos wiki-export` CLI 与 `GET /admin/knowledge-bases/{kb_id}/lint`、`POST .../wiki/export` Admin API；Wiki 导出为 Obsidian 友好 Markdown，**不回写**为真相源。

**Tech Stack:** Python 3.11、FastAPI、Typer、pytest；无新外部依赖。

**Reference:** LLM Wiki 三大操作 Ingest / Query / Lint — 本计划实现 **Lint + Export 视图**；Query 回写留作后续 Task。

## Global Constraints

- **PG Claim 仍为唯一权威**；`wiki/` 仅为导出目录，LLM 不得直接改 Wiki 文件入库
- 按 `knowledge_base_id` 隔离；Admin API 沿用 `require_admin_token` + `_resolve_active_kb`
- black max_line_length=120；snake_case；禁止 `from module import *`
- 每个 Task 含 pytest；Task 末 commit（用户未要求时不 push）
- 中文 Admin/CLI 输出摘要；代码注释英文或中文均可

---

## File Map

| 文件 | 职责 |
|------|------|
| `knowledge/lint.py` | 扫描 conflict / orphan / missing evidence / empty source 等，返回结构化报告 |
| `knowledge/lint_models.py` | `LintIssue`, `LintReport` dataclass |
| `wiki/export.py` | Claim/Source → Markdown + `[[wikilink]]` |
| `wiki/templates.py` | frontmatter 与页面命名（可选内联于 export.py，YAGNI 时合并） |
| `admin_api/routes_lint.py` | `GET .../lint` |
| `admin_api/routes_wiki.py` | `POST .../wiki/export` |
| `admin_api/schemas.py` | `LintIssueResponse`, `LintReportResponse`, `WikiExportResponse` |
| `admin_api/routes_sources.py` | 上传响应增加 `ingest_summary`（与现有 `SourceUploadResponse` 扩展） |
| `cli/main.py` | `lint`, `wiki-export` 命令 |
| `tests/test_knowledge_lint.py` | Lint 单元测试 |
| `tests/test_wiki_export.py` | 导出单元测试 |
| `tests/test_admin_lint_api.py` | Admin lint API |
| `README.md` | 新增 Lint / Wiki Export 小节 |

---

### Task 1: Lint 核心模块

**Files:**
- Create: `knowledge/lint_models.py`, `knowledge/lint.py`
- Create: `tests/test_knowledge_lint.py`

**Lint 检查项（v1）：**

| code | 说明 | 检测方式 |
|------|------|----------|
| `conflict` | 同 `family_id` 多条 `active` Claim | `get_claims_by_status("active")` 按 family 分组 |
| `missing_evidence` | active Claim 无 evidence 或 span 不在原文 | `evidence.explain` + `get_source_text` |
| `orphan_source` | source 无任何 active/staging Claim | `list_sources` vs `get_claims_for_source` |
| `quarantine_backlog` | quarantine 条目 > 0 | `list_quarantine` 计数 |
| `superseded_stale` | `superseded` Claim 仍被 retrieval 索引（可选 v1.1） | 跳过或仅报告 |

**接口：**

```python
@dataclass
class LintIssue:
    code: str
    severity: str  # warning | error
    message: str
    refs: dict[str, str]  # claim_id, source_id, family_id ...

@dataclass
class LintReport:
    kb_id: str
    checked_at: datetime
    issues: list[LintIssue]
    summary: dict[str, int]  # counts by code

def run_lint(knowledge: KnowledgePort, evidence: EvidencePort, kb_id: str) -> LintReport: ...
```

**测试：** 用 `InMemoryKnowledge` + 手工注入 conflict family；assert `LintReport.summary["conflict"] == 1`。

**Commit:** `feat: add knowledge base lint scanner`

---

### Task 2: CLI `akos lint`

**Files:**
- Modify: `cli/main.py`
- Modify: `tests/test_cli.py`（若无则 Create 最小 CLI 测试）

**行为：**

```bash
akos lint --kb legacy
akos lint --kb legacy --format json
```

输出人类可读中文摘要 + 可选 JSON。

**Commit:** `feat(cli): add akos lint command`

---

### Task 3: Admin API `GET .../lint`

**Files:**
- Create: `admin_api/routes_lint.py`
- Modify: `admin_api/schemas.py` — `LintIssueResponse`, `LintReportResponse`
- Modify: `app/main.py` — register router
- Create: `tests/test_admin_lint_api.py`

**Endpoint:**

```
GET /admin/knowledge-bases/{kb_id}/lint
→ { "summary": {...}, "issues": [...], "checked_at": "..." }
```

**Commit:** `feat(admin): expose knowledge base lint report API`

---

### Task 4: Wiki Export 模块

**Files:**
- Create: `wiki/__init__.py`, `wiki/export.py`
- Create: `tests/test_wiki_export.py`

**导出结构（对齐 LLM Wiki 命名，只读）：**

```
{output_dir}/
  index.md                 # 目录：sources + 实体列表
  log.md                   # 导出时间戳（append 或覆盖）
  source-{source_id}.md    # 文档摘要 + 引用的 Claim 列表
  {subject}.md             # 实体页：聚合该 subject 的 active Claim
```

**页面示例：**

```markdown
---
tags: [entity]
type: entity
kb_id: legacy
---

# 七天无理由

## Claims
- [[source-refund_policy_v3|refund_policy_v3]]: 排除 → 定制商品
- 运费承担方 → 买家

## 相关
- [[source-refund_policy_v3]]
```

**接口：**

```python
def export_wiki(
    knowledge: KnowledgePort,
    evidence: EvidencePort,
    kb_id: str,
    output_dir: Path,
) -> WikiExportResult:
    """Write markdown files; return counts."""
```

**约束：** 文件名 sanitize（去除 `/`）；UTF-8；不调用 LLM。

**Commit:** `feat: add read-only wiki markdown export from claims`

---

### Task 5: CLI `akos wiki-export`

**Files:**
- Modify: `cli/main.py`
- Extend: `tests/test_wiki_export.py` 或 CLI 集成测试

**行为：**

```bash
akos wiki-export --kb legacy --out ./wiki-out
# 默认: {AKOS_DATA_ROOT}/{kb_id}/wiki/
```

**Commit:** `feat(cli): add akos wiki-export command`

---

### Task 6: Admin API Wiki Export

**Files:**
- Create: `admin_api/routes_wiki.py`
- Modify: `admin_api/schemas.py` — `WikiExportRequest`, `WikiExportResponse`
- Modify: `app/main.py`
- Create: `tests/test_admin_wiki_export_api.py`

**Endpoint：**

```
POST /admin/knowledge-bases/{kb_id}/wiki/export
Body: { "output_dir": "optional relative under data root" }
→ { "files_written": 12, "output_path": "..." }
```

服务端写入 `{data_root}/{kb_id}/wiki/`，返回路径供管理台展示（F5+ 可选下载链接，本 Task 仅 API）。

**Commit:** `feat(admin): add wiki markdown export API`

---

### Task 7: 上传「复利摘要」Ingest Summary

**Files:**
- Modify: `admin_api/routes_sources.py` — 上传完成后计算摘要
- Modify: `admin_api/schemas.py` — `SourceUploadResponse.ingest_summary: str | None`
- Modify: `web/src/api/types.ts`, `SourcesPage.tsx`（可选，最小：仅 API 字段）
- Create: `tests/test_upload_ingest_summary.py`

**摘要内容（规则生成，无 LLM）：**

```python
def build_ingest_summary(results: list[ZipUploadItemResponse], knowledge) -> str:
    # 例: "新建 3 条 Claim；补充实体「七天无理由」2 条；1 条进入 quarantine"
```

逻辑：对比 upload 前后 `get_active_claims(subject)` 数量变化；quarantine 计数。

**Commit:** `feat(admin): add rule-based ingest summary on source upload`

---

### Task 8: 文档

**Files:**
- Modify: `README.md` — 「知识库 Lint / Wiki 导出」小节，引用 LLM Wiki 方法论对比表
- Modify: `.env.example` — 无需新变量

**Commit:** `docs: document lint and wiki export workflow`

---

## 验收标准

1. `akos lint --kb <id>` 对含冲突 family 的库报告 `conflict`
2. `akos wiki-export --out /tmp/wiki` 生成 `index.md` 与至少一个实体页，Obsidian 可打开
3. `GET /admin/knowledge-bases/{kb_id}/lint` 返回 JSON 与 CLI 一致
4. 上传文档后 API 响应含 `ingest_summary` 非空（有 Claim 时）
5. `pytest tests/test_knowledge_lint.py tests/test_wiki_export.py tests/test_admin_lint_api.py -v` 全绿

## 明确不做（本 Plan）

- LLM 自动维护 Wiki 文件（Ingest 写多个 md）
- Query 回写为新 Claim（留 `docs/superpowers/plans/2026-xx-akos-query-writeback.md`）
- 管理台 Wiki 浏览页（可 F5+ 读 export 目录）
- 真 embedding / qmd 集成

## 与 LLM Wiki 对照

| LLM Wiki | 本 Plan |
|----------|---------|
| Lint 口头指令 | `akos lint` + Admin API |
| wiki/ 目录 | `wiki-export` 从 Claim 生成 |
| Ingest 更新已有页 | Task 7 规则摘要（v1）；LLM delta merge 后续 |
| Query 回写 | Out of scope |

---

## 建议执行顺序

Task 1 → 2 → 3（Lint 闭环）→ Task 4 → 5 → 6（Export 闭环）→ Task 7 → Task 8
