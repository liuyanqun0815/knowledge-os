# AKOS Hybrid LLM Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现规则同步入库 + LLM 后台切片补抽：任意文本文档覆盖更丰富 Claim；未知谓词 quarantine；关闭 LLM 时行为与现网一致。

**Architecture:** 同步 `ingest_graph` 仍只用领域 `RuleExtractor`（或空规则）。上传成功后 `BackgroundTasks` 调用 `EnrichmentRunner`：`TextChunker` 切片 → `DomainLlmExtractor` → 去重写入 Compiler 路径。进程 lifespan 扫描 `enriching` 重试。不做 Redis Worker。

**Tech Stack:** Python 3.11+、FastAPI BackgroundTasks、现有 OpenAiCompatibleClient、pytest、black(120)

**Spec:** `docs/superpowers/specs/2026-09-09-akos-hybrid-llm-extraction-design.md`

**Out of scope:** Redis 队列、PDF OCR、未知谓词自动入正式 Ontology、同步 Full Hybrid

## Global Constraints

- 保持 Source→Claim→Evidence；禁止把系统做成纯 Chunk-RAG
- **禁止**在同步 `compile_node` 内调用 LLM
- 未知谓词 → quarantine(`unknown_predicate`)，不直接 active
- `family_id` 与 `KnowledgeCompiler._family_id` 一致
- Settings 使用 `AKOS_` 前缀（pydantic-settings）
- 无 `AKOS_LLM_API_KEY` 时跳过补抽
- 每个 Task：相关测试 PASS + git commit
- black max_line_length=120；禁止 `from module import *`；snake_case

---

## File Structure

```text
compiler/
├── chunker.py
├── domain_llm_extractor.py
├── enrichment.py
├── hybrid_extractor.py          # 可选组合；同步默认不用 LLM 侧
├── extraction_spec.py           # LlmExtractionSpec dataclass
├── service.py                   # + apply_extracted_claims(...)
├── rule_extractor.py
└── llm_extractor.py             # 委托 DomainLlmExtractor 或保留薄封装

domains/
├── base.py                      # + llm_extraction_spec()
├── ecommerce_cs/domain.py
├── corporate_culture/domain.py
├── generic/domain.py
└── loan_finance/domain.py

infra/settings.py                # extract_* / chunk_* / min_confidence
app/main.py                      # lifespan resume enriching
admin_api/
├── routes_sources.py            # BackgroundTasks after upload
├── schemas.py                   # SourceResponse enrichment fields
└── source_helpers.py

tests/
├── test_chunker.py
├── test_domain_llm_extractor.py
├── test_enrichment_runner.py
├── test_hybrid_extraction_api.py
```

---

### Task 1: Settings + LlmExtractionSpec + DomainPort 扩展

**Files:**
- Modify: `infra/settings.py`, `.env.example`
- Create: `compiler/extraction_spec.py`
- Modify: `domains/base.py` 及各 domain 最小实现（可先返回空 pred 列表的 stub，Task 5 填全）
- Test: `tests/test_extraction_settings.py`

**Interfaces:**
- Produces: `Settings.extract_rules`, `extract_llm`, `chunk_max_chars`, `chunk_max_per_doc`, `extract_min_confidence`
- Produces: `LlmExtractionSpec(allowed_predicates, entity_types, few_shot_hints)`
- Produces: `DomainPort.llm_extraction_spec() -> LlmExtractionSpec`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_extraction_settings.py
from infra.settings import Settings

def test_extraction_settings_defaults():
    s = Settings(
        _env_file=None,
        llm_api_key="",
    )
    assert s.extract_rules is True
    assert s.extract_llm is True
    assert s.chunk_max_chars == 3000
    assert s.chunk_max_per_doc == 40
    assert s.extract_min_confidence == 0.5
```

（若 Settings 强制读 `.env`，测试里用 `Settings(extract_rules=True, ...)` 显式传入覆盖。）

- [ ] **Step 2: 跑测确认失败 → 实现 settings 字段与 extraction_spec → 全绿 → Commit**

```bash
pytest tests/test_extraction_settings.py -v
git add infra/settings.py .env.example compiler/extraction_spec.py domains/
git commit -m "feat: add hybrid extraction settings and LlmExtractionSpec"
```

默认值（写入 `.env.example` 注释）：

```text
AKOS_EXTRACT_RULES=true
AKOS_EXTRACT_LLM=true
AKOS_CHUNK_MAX_CHARS=3000
AKOS_CHUNK_MAX_PER_DOC=40
AKOS_EXTRACT_MIN_CONFIDENCE=0.5
```

---

### Task 2: TextChunker

**Files:**
- Create: `compiler/chunker.py`
- Test: `tests/test_chunker.py`

**Interfaces:**
- Produces: `chunk_text(text, max_chars, max_chunks) -> list[str]`  
  - 优先按空行/Markdown 标题切；超长段再硬切  
  - 超过 `max_chunks` 的丢弃，返回值附带或由调用方检测 `truncated=True`（可用返回 `ChunkResult(chunks, truncated: bool)`）

- [ ] **Step 1: 失败测试**

```python
from compiler.chunker import chunk_text

def test_chunk_respects_max_chars_and_max_chunks():
    text = ("段落A\n\n" * 5) + ("X" * 5000)
    result = chunk_text(text, max_chars=1000, max_chunks=3)
    assert len(result.chunks) <= 3
    assert all(len(c) <= 1000 for c in result.chunks)
    assert result.truncated is True
```

- [ ] **Step 2–5: 实现、测通、Commit**

```bash
git commit -m "feat: add text chunker with hard per-doc limits"
```

---

### Task 3: DomainLlmExtractor（通用，取代写死 corporate）

**Files:**
- Create: `compiler/domain_llm_extractor.py`
- Modify: `compiler/llm_extractor.py` — `create_corporate_extractor` 改为基于 DomainLlmExtractor + corporate spec（保持兼容）
- Modify: `domains/corporate_culture/domain.py` — `llm_extraction_spec()` 填倡导/禁止/适用于
- Test: `tests/test_domain_llm_extractor.py`

**Interfaces:**
- Produces: `DomainLlmExtractor(client, spec: LlmExtractionSpec).extract(text) -> list[ExtractedClaim]`
- Prompt 必须包含 `allowed_predicates` 与 JSON schema；quote 必须能在原文 `find`

- [ ] **Step 1: mock client 返回固定 JSON 的测试**

```python
def test_domain_llm_extractor_parses_claims_and_spans(monkeypatch):
    # fake client.chat_completions returns JSON list with quote substring of text
    ...
    claims = extractor.extract("公司倡导诚信经营。")
    assert claims[0].predicate == "倡导"
    assert claims[0].quote in "公司倡导诚信经营。"
```

- [ ] **Step 2: 未知谓词仍返回 ExtractedClaim（由 Compiler/Enrichment 决定 quarantine）— 抽取器不过滤白名单之外的结果，或可选 filter；规格：校验在写入侧**

推荐：**抽取器返回原始结构；EnrichmentRunner/Compiler 做白名单裁决**，便于测 quarantine。

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: add domain-scoped LLM extractor with injectable spec"
```

---

### Task 4: KnowledgeCompiler.apply_extracted_claims（补抽写入 + 去重）

**Files:**
- Modify: `compiler/service.py`
- Test: `tests/test_compiler_apply_extracted.py`

**Interfaces:**
- Produces:

```python
def apply_extracted_claims(
    self,
    source_id: str,
    extracted: list[ExtractedClaim],
    *,
    staging: bool = False,
    min_confidence: float = 0.5,
    existing_skip: bool = True,
) -> CompileReport:
    ...
```

行为对齐规格 §4.1：

- confidence < min → quarantine(`low_confidence`)
- quote 不在原文 → quarantine(`span_missing`)
- ontology validate 失败 → quarantine(`invalid_predicate` / unknown)
- 同 family+object 已存在 → skip
- 同 family 不同 object 且已有 active → 新 claim `staging`（或 quarantine 记录冲突；优先 **staging** 按规格）
- 成功路径：append_claim、graph、evidence、index（非 staging）

- [ ] **Step 1–5: TDD + Commit**

```bash
git commit -m "feat: apply extracted claims with dedupe and quarantine rules"
```

---

### Task 5: EnrichmentRunner

**Files:**
- Create: `compiler/enrichment.py`
- Test: `tests/test_enrichment_runner.py`

**Interfaces:**
- Produces:

```python
def enrich_source(
    *,
    kb_id: str,
    source_id: str,
    deps,  # orchestrator deps or structured EnrichDeps
    settings: Settings,
) -> None:
```

逻辑：

1. 若 `not settings.extract_llm` 或 client 未配置 → 设 source status `succeeded`，enrichment skipped；return  
2. 设 status `enriching`  
3. `chunk_text` → 逐片 `DomainLlmExtractor.extract`；片失败重试 1 次  
4. `compiler.apply_extracted_claims(...)`  
5. 若 truncated 或失败片 ≥50% → `succeeded_partial`；否则 `succeeded`  
6. 持久化进度：可用 source 扩展字段或旁路 metadata 表；**最小实现**：把计数写进 source.status 旁路——若 Source 模型仅有 `status` 字符串，则：  
   - status ∈ {`enriching`,`succeeded`,`succeeded_partial`,`failed`,`ready`}  
   - 计数经 `SourceResponse` 从 claims/quarantine 现算（`claims_from_llm` 可用 quarantine/claim 时间近似，或 Task 6 给 Claim 加 `extraction_origin` 可选字段）

**最小可验收**：status 状态机正确 + quarantine 出现；计数可在 list sources 时用 claims_count 差值或简单字段。

建议 Claim 增加可选 `origin: str = "rule"|"llm"`（若改动面大，可用 quarantine payload / CompileReport 日志先验收，计数 API 后续）。

本 Task 要求至少：

- `knowledge.update_source_status(source_id, status)`（若尚无则加）  
- enrich 后 claims 增多（mock LLM）

- [ ] **Step 1–5: TDD + Commit**

```bash
git commit -m "feat: add EnrichmentRunner for async LLM backfill"
```

---

### Task 6: 上传接线 BackgroundTasks + lifespan 重试

**Files:**
- Modify: `admin_api/routes_sources.py` — upload 成功后 `background_tasks.add_task(...)`
- Modify: `app/main.py` — lifespan 扫描 enriching
- Modify: `admin_api/schemas.py`, `source_helpers.py` — 可选 enrichment 字段
- Test: `tests/test_hybrid_extraction_api.py`

**Interfaces:**
- 同步 ingest **不得**调用 LLM（测试可用 spy）
- LLM 开启时 upload 返回后 source 最终变为 enriching→succeeded（TestClient 可直接调 `enrich_source` 模拟后台，或 `BackgroundTasks` 在 TestClient 中会执行）

- [ ] **Step 1: 测试**

```python
def test_upload_schedules_enrichment_without_blocking_on_llm(monkeypatch):
    # spy DomainLlmExtractor.extract / OpenAiCompatibleClient — must not be called in upload request path
    # then manually run enrich_source and assert extra claims
    ...
```

```python
def test_unknown_predicate_goes_to_quarantine(monkeypatch):
    # mock LLM returns predicate not in ecommerce whitelist
    ...
```

- [ ] **Step 2–5: 实现、测通、Commit**

```bash
git commit -m "feat: wire async LLM enrichment after source upload"
```

---

### Task 7: 各领域 llm_extraction_spec 填实 + generic 宽谓词

**Files:**
- Modify: `domains/ecommerce_cs/domain.py`（谓词与种子一致）
- Modify: `domains/corporate_culture/domain.py`
- Modify: `domains/generic/domain.py` — 规定/适用于/禁止/要求；规则可为 `RuleExtractor()` 或空抽取器
- Modify: `domains/loan_finance/domain.py` — 最小占位 spec
- Test: `tests/test_domain_extraction_specs.py`

- [ ] **Step 1–5: 断言各 domain spec 非空谓词；Commit**

```bash
git commit -m "feat: define per-domain LLM extraction specs"
```

---

### Task 8: 验收文档与开关回归

**Files:**
- Modify: `README.md`、`.env.example` — 说明两段式抽取与开关
- Test: 确保 `AKOS_EXTRACT_LLM=false` 时 `tests/test_e2e_sample.py` / admin upload 相关测例仍过

- [ ] **Step 1: 跑回归**

```bash
pytest tests/test_chunker.py tests/test_domain_llm_extractor.py tests/test_enrichment_runner.py tests/test_hybrid_extraction_api.py tests/test_compiler_apply_extracted.py -v
AKOS_EXTRACT_LLM=false pytest tests/test_e2e_sample.py tests/test_admin_kb_api.py -v --tb=short
```

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: document hybrid LLM enrichment and verify rule-only regression"
```

---

## Spec Coverage Checklist

| Spec 项 | Task |
|---------|------|
| Hybrid 开关 | 1, 6, 8 |
| DomainLlmExtractor | 3, 7 |
| TextChunker 硬上限 | 2, 5 |
| 同步仅规则 | 6 |
| BackgroundTasks + enriching 重试 | 5, 6 |
| 去重 / unknown_predicate / span / confidence | 4, 5 |
| 状态机 succeeded_partial | 5, 6 |
| 领域 spec | 7 |
| 验收与回归 | 8 |
| Redis Worker / OCR | 明确不做 |

## Self-Review Notes

- Settings 字段名用 snake_case，环境变量自动 `AKOS_EXTRACT_LLM`  
- 同步路径继续 `domain.get_extractor()` = Rule；不要把 Hybrid(LLM) 挂进 compile_node  
- FastAPI `TestClient` 默认会跑 BackgroundTasks；若测「上传路径未调 LLM」，在 add_task 前 spy 或暂时 mock add_task  

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-09-akos-hybrid-llm-extraction.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每 Task 新开子代理，任务间审查  
2. **Inline Execution** — 本会话按 executing-plans 连续执行  

Which approach?
