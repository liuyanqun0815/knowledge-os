# Compiled Wiki Layer + Three-Way Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist an incremental compiled wiki under each KB (`data/.../kb/{kb_id}/wiki/`), purge stale chunks, and fuse Claim + Wiki topic pages + source Chunks in Ask retrieval.

**Architecture:** After chunk save, hard-delete stale rows. After enrich/topic rebuild, `wiki.compile` upserts `topic-*.md` with `[[wikilinks]]` and `.meta/pages.json`. A small `WikiPageRetrieval` indexes topic pages; `HybridRetrieval` / fusion extend to three-way RRF. Synthesis accepts wiki excerpts but grounds facts on claims/source chunks.

**Tech Stack:** Python 3, existing KnowledgePort/ChunkRetrieval/HybridRetrieval, FastAPI admin, pytest, Vite admin UI (chunk panel default active-only).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-14-akos-compiled-wiki-retrieval-design.md` (confirmed)
- Same KB compile layer only — no second wiki KB; do not delete original Sources
- Three-way fusion (A); wiki must not be sole truth source for numbers/rules
- Default: `AKOS_PURGE_STALE_CHUNKS=true`, `AKOS_WIKI_COMPILE=true`; `AKOS_WIKI_LINK_EXPAND=false` (P2)
- black `max_line_length=120`; no `from module import *`; TDD; commit after each task
- Dirty tree: stage only task files; save/restore WIP on shared files

## File map

| File | Responsibility |
|------|----------------|
| `infra/settings.py`, `.env.example`, `README.md` | new flags + weights |
| `knowledge/ports.py`, `memory_repo.py`, `infra/pg_repos.py` | `purge_stale_chunks(source_id)` / save_chunks hooks |
| `compiler/chunk_service.py` | ensure purge after reindex path |
| `wiki/paths.py` | resolve compile root `{data_root}/kb/{kb_id}/wiki` |
| `wiki/meta.py` | read/write `.meta/pages.json` |
| `wiki/compile.py` | incremental topic page update (template + optional LLM) |
| `wiki/prompts.py` | LLM merge prompt (role/goal/rules/output/context) |
| `retrieval/wiki_index.py` | index/search compiled topic pages |
| `retrieval/fusion.py`, `retrieval/hybrid.py` | three-way fuse |
| `orchestrator/synthesis.py` | include wiki excerpts in prompt |
| `compiler/chunk_enrichment.py` | trigger compile after enrich |
| `admin_api/routes_wiki.py` (+ schemas) | compile + purge-stale endpoints |
| `web/src/components/SourceChunksPanel.tsx` | default active-only listing |
| `tests/test_purge_stale_chunks.py`, `tests/test_wiki_compile.py`, `tests/test_wiki_retrieval.py`, … | coverage |

---

### Task 1: Settings for purge + wiki compile + retrieval weights

**Files:**
- Modify: `infra/settings.py`
- Modify: `.env.example`
- Modify: `README.md` (env table rows only)
- Test: `tests/test_wiki_compile_settings.py` (new)

**Interfaces:**
- Produces: `Settings.purge_stale_chunks: bool = True`, `wiki_compile: bool = True`, `wiki_compile_llm: bool = True`, `retrieval_claim_weight: float = 1.0`, `retrieval_wiki_weight: float = 0.9`, `retrieval_chunk_weight: float = 0.8`, `wiki_link_expand: bool = False`

- [ ] **Step 1: Failing test** — defaults as above (`_env_file=None` or delenv)

- [ ] **Step 2: Run** `pytest tests/test_wiki_compile_settings.py -q` — expect FAIL

- [ ] **Step 3: Implement settings + `.env.example` comments**

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** `feat: add compiled wiki and purge-stale settings`

---

### Task 2: Purge stale chunks after save

**Files:**
- Modify: `knowledge/ports.py` — optional explicit `purge_stale_chunks(source_id: str) -> int` **or** fold into `save_chunks`
- Modify: `knowledge/memory_repo.py`, `infra/pg_repos.py`
- Modify: `compiler/chunk_service.py` if purge must run after index (prefer inside `save_chunks` when `settings` not available: always purge after write; gate via caller passing flag OR always-on in repo when env read is undesirable — **prefer**: `save_chunks` always deletes remaining stale rows; settings gate in `index_source_chunks` / service layer)
- Test: `tests/test_purge_stale_chunks.py`, update `tests/test_knowledge.py` / pg chunk reindex tests if they expected stale leftovers

**Interfaces:**
- Consumes: existing `mark_chunks_stale` + `save_chunks`
- Produces: after save, no `status=stale` rows for that `source_id`; return/delete embeddings for purged chunk ids (PG)

**Recommended behavior:**

```python
def save_chunks(...):
    mark_chunks_stale(source_id)
    # upsert new actives
    if purge_enabled:  # from settings at call site OR always purge (spec default true)
        delete_stale_chunks(source_id)
```

Call site: `index_source_chunks` / segmentation apply reads `settings.purge_stale_chunks`.

- [ ] **Step 1: Failing test** — save fewer chunks than before → stale count 0; old ids gone

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement memory + PG delete stale (+ embeddings)**

- [ ] **Step 4: PASS** + update any tests that asserted stale retention

- [ ] **Step 5: Commit** `fix: purge stale chunks after reindex`

---

### Task 3: Wiki compile paths + meta store

**Files:**
- Create: `wiki/paths.py` — `compile_wiki_root(data_root: str | Path, kb_id: str) -> Path`
- Create: `wiki/meta.py` — `WikiPageMeta`, `load_pages_meta`, `save_pages_meta`
- Test: `tests/test_wiki_paths_meta.py`

**Interfaces:**
- Produces: root `.../kb/{kb_id}/wiki`; meta file `.meta/pages.json` mapping `page_id -> {path, title, kind, content_hash, source_ids, updated_at}`

- [ ] **Step 1–5: TDD + commit** `feat: add compiled wiki path and pages meta`

---

### Task 4: Template incremental topic compile (no LLM required)

**Files:**
- Create: `wiki/compile.py` — `compile_topics_for_source(knowledge, kb_id, source_id, data_root, settings, graph=None) -> CompileReport`
- Reuse: topic naming helpers from `wiki/export.py` (`_topic_page_name`, `_topic_wikilink`, `_source_wikilink`) — extract shared helpers to `wiki/links.py` if needed to avoid circular imports
- Wire: `compiler/chunk_enrichment.py` end — if `settings.wiki_compile`: call compile
- Test: `tests/test_wiki_compile.py`

**Interfaces:**
- Consumes: active chunks for source (topics), `list_topic_clusters`, active claims optionally
- Produces: `topic-*.md` + updated `index.md` topic section + meta; `CompileReport(pages_written=int, topics=list[str])`

**Template page sections:** 摘要（可空）/ 相关 Chunk 要点 / Claims / 相关原文 links / 相关主题 links

- [ ] **Step 1: Failing test** — two sources sharing topic → one topic file contains both source wikilinks

- [ ] **Step 2–4: Implement + PASS**

- [ ] **Step 5: Commit** `feat: incrementally compile topic wiki pages`

---

### Task 5: Optional LLM merge for topic pages

**Files:**
- Create: `wiki/prompts.py` — structured prompt (角色/目标/规则/输出/上下文)
- Modify: `wiki/compile.py` — if `wiki_compile_llm` and client configured, merge old body + new evidence
- Test: `tests/test_wiki_compile_llm.py` with FakeLlmClient

**Interfaces:**
- Produces: LLM path preserves required `[[wikilink]]` blocks; falls back to template on parse failure

- [ ] **Step 1–5: TDD + commit** `feat: optional LLM merge for compiled topic pages`

---

### Task 6: WikiPageRetrieval index + search

**Files:**
- Create: `retrieval/wiki_index.py` — `WikiPageRetrieval.index_wiki_root(root)`, `search(query, top_k) -> list[Hit]` (reuse BM25/char-hash patterns from chunk index if possible)
- Modify: `infra/bootstrap.py` / orchestrator deps — attach `wiki_retrieval` when compile enabled
- Test: `tests/test_wiki_retrieval.py`

**Interfaces:**
- Hit payload includes `ref_type="wiki"`, `ref_id=page_id`, `title`, `path`, `text` excerpt
- Reindex: call after compile for touched pages (or full root scan)

- [ ] **Step 1–5: TDD + commit** `feat: index compiled wiki topic pages for retrieval`

---

### Task 7: Three-way fusion in Ask path

**Files:**
- Modify: `retrieval/fusion.py` — `fuse_hits_three(...)` or generalize `fuse_hits` to N lists + weights
- Modify: `retrieval/hybrid.py` / ask nodes — run wiki search when available; pass weights from settings
- Modify: `orchestrator/synthesis.py` — add wiki excerpts section; cite `wiki`
- Test: `tests/test_fusion.py` (or new), `tests/test_retrieval.py`, `tests/test_synthesis.py` as needed

**Interfaces:**
- Consumes: claim_hits, wiki_hits, chunk_hits + weights
- Produces: fused ranking; synthesis prompt includes `## Wiki 主题页` with grounding rule

- [ ] **Step 1: Failing test** — wiki-only strong hit appears in fused top when claim/chunk weak

- [ ] **Step 2–4: Implement + PASS**

- [ ] **Step 5: Commit** `feat: fuse claim, wiki, and chunk hits in ask retrieval`

---

### Task 8: Admin APIs + UI chunk default + docs

**Files:**
- Modify: `admin_api/routes_wiki.py` / schemas — `POST .../wiki/compile`, `POST .../chunks/purge-stale` (chunks route may live on `routes_sources.py`)
- Modify: `web/src/components/SourceChunksPanel.tsx` (+ API) — default `status=active`
- Modify: `README.md` — document compile layer path + flags
- Test: `tests/test_admin_wiki_compile_api.py`, frontend test if exists

- [ ] **Step 1–5: TDD + commit** `feat: add wiki compile and purge-stale admin APIs`

---

### Task 9: Regression sweep

- [ ] **Step 1: Run**

```bash
pytest tests/test_wiki_compile_settings.py tests/test_purge_stale_chunks.py tests/test_wiki_paths_meta.py tests/test_wiki_compile.py tests/test_wiki_compile_llm.py tests/test_wiki_retrieval.py tests/test_fusion.py tests/test_retrieval.py tests/test_synthesis.py tests/test_wiki_export.py -q
```

Plus admin API tests added in Task 8.

- [ ] **Step 2: Fix failures**

- [ ] **Step 3: Commit only if fixes** `test: compiled wiki retrieval regression`

---

## Spec coverage

| Spec item | Task |
|-----------|------|
| Purge stale chunks | 2, 8 |
| Compile root + meta | 3 |
| Incremental topic pages + links | 4, 5 |
| Wiki index | 6 |
| Three-way fusion + synthesis | 7 |
| Settings / API / UI | 1, 8 |
| Acceptance / regression | 9 |

## Out of scope

- Second wiki KB, WYSIWYG editor, physical merge into one Source file
- `AKOS_WIKI_LINK_EXPAND` one-hop (P2 — stub setting only in Task 1)
- Replacing TopicCluster algorithm
