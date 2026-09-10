# Open Predicate LLM Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow LLM extraction to invent predicates beyond domain whitelists, persist qualifying claims as active after quote/confidence gates, and lazily register new predicates into the in-memory ontology.

**Architecture:** `AKOS_EXTRACT_OPEN_PREDICATES` (default `true`) flips `LlmExtractionSpec.open_predicates`. `DomainLlmExtractor` emits an open-mode prompt with `suggested_*` fields. `KnowledgeCompiler.apply_extracted_claims(..., open_predicates=...)` registers unknown `(subject_type, predicate, object_type)` instead of quarantining `invalid_predicate`. Enrichment and sync LLM extract paths pass the settings flag into both prompt and apply.

**Tech Stack:** Python 3, Pydantic Settings, FastAPI enrichment BackgroundTasks, pytest, existing `InMemoryOntology` / `KnowledgeCompiler`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-10-akos-open-predicate-extraction-design.md`
- Default `AKOS_EXTRACT_OPEN_PREDICATES=true`; `false` restores whitelist hard-reject
- Quality gates unchanged: `quote in source_text`, `confidence >= extract_min_confidence`
- RuleExtractor path unchanged (no open lazy-register on pure rule ingest beyond existing Concept↔Concept)
- Do not put LLM into sync `compile_node` beyond existing hybrid/intersect behavior
- black formatting, `max_line_length=120`; no `from module import *`
- TDD: failing test first for each task; commit after each task green

## File map

| File | Responsibility |
|------|----------------|
| `infra/settings.py` | `extract_open_predicates: bool = True` |
| `.env.example` | Document `AKOS_EXTRACT_OPEN_PREDICATES` |
| `compiler/extraction_spec.py` | `open_predicates: bool = False` on `LlmExtractionSpec` |
| `compiler/domain_llm_extractor.py` | Open vs closed prompt configuration JSON |
| `compiler/extraction_settings.py` (create) or small helper in `enrichment.py` | `spec_with_open_flag(domain, settings) -> LlmExtractionSpec` |
| `compiler/enrichment.py` | Pass open flag into extractor + `apply_extracted_claims` |
| `compiler/intersect.py` | Pass open flag into `DomainLlmExtractor` when extracting LLM claims |
| `compiler/service.py` | Lazy `register_predicate` when `open_predicates` and validate fails |
| `tests/test_extraction_settings.py` | Settings field |
| `tests/test_domain_llm_extractor.py` | Open prompt assertions |
| `tests/test_compiler_apply_extracted.py` | Open accept + closed quarantine |
| `tests/test_hybrid_extraction_api.py` / `tests/test_enrichment_runner.py` | Enrichment end-to-end with open default |

---

### Task 1: Settings + LlmExtractionSpec flag

**Files:**
- Modify: `infra/settings.py`
- Modify: `.env.example`
- Modify: `compiler/extraction_spec.py`
- Modify: `tests/test_extraction_settings.py`

**Interfaces:**
- Consumes: none
- Produces: `Settings.extract_open_predicates: bool` (env `AKOS_EXTRACT_OPEN_PREDICATES`, default `True`); `LlmExtractionSpec.open_predicates: bool = False`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_extraction_settings.py`:

```python
def test_settings_extract_open_predicates_defaults_true(monkeypatch):
    monkeypatch.delenv("AKOS_EXTRACT_OPEN_PREDICATES", raising=False)
    from infra.settings import Settings

    assert Settings().extract_open_predicates is True


def test_llm_extraction_spec_open_predicates_default_false():
    from compiler.extraction_spec import LlmExtractionSpec

    spec = LlmExtractionSpec(allowed_predicates=["适用"], entity_types=["Concept"])
    assert spec.open_predicates is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_settings.py::test_settings_extract_open_predicates_defaults_true tests/test_extraction_settings.py::test_llm_extraction_spec_open_predicates_default_false -q`

Expected: FAIL (`extract_open_predicates` missing / `open_predicates` missing)

- [ ] **Step 3: Minimal implementation**

In `infra/settings.py` under Hybrid 抽取:

```python
extract_open_predicates: bool = True
```

In `compiler/extraction_spec.py`:

```python
@dataclass
class LlmExtractionSpec:
    allowed_predicates: list[str]
    entity_types: list[str]
    prompt_locale: str = "zh"
    few_shot_hints: list[str] | None = None
    open_predicates: bool = False
```

In `.env.example` after `AKOS_EXTRACT_MIN_CONFIDENCE`:

```bash
# true=LLM 可自创谓词并懒注册；false=名单外进 quarantine
AKOS_EXTRACT_OPEN_PREDICATES=true
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_extraction_settings.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infra/settings.py .env.example compiler/extraction_spec.py tests/test_extraction_settings.py
git commit -m "feat: add extract_open_predicates settings and spec flag"
```

---

### Task 2: Open-mode DomainLlmExtractor prompt

**Files:**
- Modify: `compiler/domain_llm_extractor.py`
- Modify: `tests/test_domain_llm_extractor.py`

**Interfaces:**
- Consumes: `LlmExtractionSpec.open_predicates`
- Produces: When `open_predicates=True`, prompt configuration uses `mode=open`, `suggested_predicates`, `suggested_entity_types`, and a rule allowing predicates outside the suggested list; when `False`, keep existing `allowed_predicates` / `entity_types` keys for compatibility

- [ ] **Step 1: Write the failing test**

Add to `tests/test_domain_llm_extractor.py`:

```python
def test_open_prompt_uses_suggested_predicates_and_allows_novel() -> None:
    client = FakeLlmClient([])
    spec = LlmExtractionSpec(
        allowed_predicates=["倡导", "禁止"],
        entity_types=["Value", "Behavior"],
        open_predicates=True,
    )
    DomainLlmExtractor(client, spec).extract("公司倡导诚信经营。")
    prompt = client.messages[0]["content"]
    assert '"mode": "open"' in prompt
    assert '"suggested_predicates"' in prompt
    assert "不必限于" in prompt or "不必限" in prompt
    assert '"allowed_predicates"' not in prompt
```

Keep existing `test_prompt_contains_spec_and_json_schema` (closed mode) unchanged.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_domain_llm_extractor.py::test_open_prompt_uses_suggested_predicates_and_allows_novel -q`

Expected: FAIL (prompt still emits `allowed_predicates`)

- [ ] **Step 3: Minimal implementation**

Update `DomainLlmExtractor._build_prompt` in `compiler/domain_llm_extractor.py`:

```python
def _build_prompt(self, text: str) -> str:
    if self._spec.open_predicates:
        configuration = {
            "mode": "open",
            "suggested_predicates": self._spec.allowed_predicates,
            "suggested_entity_types": self._spec.entity_types,
            "prompt_locale": self._spec.prompt_locale,
            "few_shot_hints": self._spec.few_shot_hints or [],
            "rules": [
                "可使用最贴切的中文谓词，不必限于 suggested_predicates",
                "quote 必须是原文连续非空子串",
                "只输出匹配 json_schema 的 JSON 数组",
            ],
        }
    else:
        configuration = {
            "allowed_predicates": self._spec.allowed_predicates,
            "entity_types": self._spec.entity_types,
            "prompt_locale": self._spec.prompt_locale,
            "few_shot_hints": self._spec.few_shot_hints or [],
        }
    return _PROMPT.format(
        configuration=json.dumps(configuration, ensure_ascii=False),
        json_schema=json.dumps(_CLAIM_JSON_SCHEMA, ensure_ascii=False),
        text=text,
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_domain_llm_extractor.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add compiler/domain_llm_extractor.py tests/test_domain_llm_extractor.py
git commit -m "feat: open-mode LLM extraction prompt with suggested predicates"
```

---

### Task 3: Compiler lazy-register unknown predicates

**Files:**
- Modify: `compiler/service.py` (`apply_extracted_claims`)
- Modify: `tests/test_compiler_apply_extracted.py`

**Interfaces:**
- Consumes: `OntologyPort.register_predicate`, `OntologyPort.validate_claim`
- Produces: `apply_extracted_claims(..., open_predicates: bool = False)`; when `open_predicates=True` and validate fails, call `register_predicate(subject_type, predicate, object_type)` then continue write path; when `False`, keep `invalid_predicate` quarantine

- [ ] **Step 1: Write the failing tests**

Update/add in `tests/test_compiler_apply_extracted.py`:

```python
def test_apply_extracted_claims_quarantines_invalid_predicate():
    # existing test — pass open_predicates=False explicitly for clarity
    ...
    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted(predicate="未知关系", quote="七天无理由支持未知关系买家")],
        open_predicates=False,
    )
    ...


def test_apply_extracted_claims_open_registers_and_writes_novel_predicate():
    compiler, knowledge, graph, evidence, retrieval = _build_compiler(
        text="七天无理由支持未知关系买家。"
    )
    report = compiler.apply_extracted_claims(
        "source-1",
        [_extracted(predicate="未知关系", quote="七天无理由支持未知关系买家")],
        open_predicates=True,
    )
    assert report.claims_created == 1
    assert report.quarantined == 0
    assert knowledge.list_quarantine() == []
    claim = next(c for c in knowledge.get_claims_by_status("active") if c.predicate == "未知关系")
    assert claim.subject == "七天无理由"
    assert compiler.ontology.validate_claim("Policy", "未知关系", "Party")
    hits = retrieval.search("未知关系", RetrievalMode.CLAIM, {})
    assert any(h.claim_id == claim.id for h in hits)
```

- [ ] **Step 2: Run open test to verify it fails**

Run: `pytest tests/test_compiler_apply_extracted.py::test_apply_extracted_claims_open_registers_and_writes_novel_predicate -q`

Expected: FAIL (`open_predicates` unexpected kwarg or still quarantined)

- [ ] **Step 3: Minimal implementation**

In `apply_extracted_claims` signature add `open_predicates: bool = False`.

Replace validate-fail branch:

```python
if not self._ontology.validate_claim(subject_type, candidate.predicate, object_type):
    if open_predicates:
        self._ontology.register_predicate(subject_type, candidate.predicate, object_type)
    else:
        self._knowledge.add_quarantine("invalid_predicate", raw)
        quarantined += 1
        continue
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_compiler_apply_extracted.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add compiler/service.py tests/test_compiler_apply_extracted.py
git commit -m "feat: lazy-register novel predicates when open_predicates enabled"
```

---

### Task 4: Wire settings into enrichment + intersect LLM extract

**Files:**
- Create: `compiler/spec_utils.py` (tiny helper)
- Modify: `compiler/enrichment.py`
- Modify: `compiler/intersect.py`
- Modify: `tests/test_hybrid_extraction_api.py`
- Modify: `tests/test_enrichment_runner.py` (if it asserts `invalid_predicate`)

**Interfaces:**
- Consumes: `Settings.extract_open_predicates`, `domain.llm_extraction_spec()`
- Produces: `def apply_open_flag(spec: LlmExtractionSpec, settings: Settings) -> LlmExtractionSpec` returning a copy/replaced dataclass with `open_predicates=settings.extract_open_predicates`; enrichment calls `apply_extracted_claims(..., open_predicates=settings.extract_open_predicates)`

- [ ] **Step 1: Write the failing test**

In `tests/test_hybrid_extraction_api.py`, change the unknown-predicate enrich case to expect **active claim** under default open settings (or set env true), and add a closed-mode case:

```python
def test_enrich_open_predicates_writes_novel_claim(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_OPEN_PREDICATES", "true")
    # ... same upload + mock extract_unknown as existing test ...
    task(**kwargs)
    knowledge = kwargs["deps"].knowledge
    assert knowledge.get_source(kwargs["source_id"]).status == "succeeded"
    active = [c for c in knowledge.get_claims_by_status("active") if c.predicate == "unknown_predicate"]
    assert active
    assert not any(q["reason"] == "invalid_predicate" for q in knowledge.list_quarantine())


def test_enrich_closed_predicates_quarantines_novel_claim(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_EXTRACT_OPEN_PREDICATES", "false")
    # ... same mock ...
    task(**kwargs)
    assert kwargs["deps"].knowledge.list_quarantine()[-1]["reason"] == "invalid_predicate"
```

Adapt fixtures from existing `test_hybrid_extraction_api` enrich scheduling test (keep structure; do not invent a different upload flow).

- [ ] **Step 2: Run open enrich test — expect FAIL**

Run: `pytest tests/test_hybrid_extraction_api.py -k "open_predicates or closed_predicates" -q`

Expected: FAIL until wiring lands (still quarantine under open)

- [ ] **Step 3: Implement helper + wire**

`compiler/spec_utils.py`:

```python
from __future__ import annotations

from dataclasses import replace

from compiler.extraction_spec import LlmExtractionSpec
from infra.settings import Settings


def apply_open_flag(spec: LlmExtractionSpec, settings: Settings) -> LlmExtractionSpec:
    return replace(spec, open_predicates=settings.extract_open_predicates)
```

`compiler/enrichment.py`:

```python
from compiler.spec_utils import apply_open_flag
...
spec = apply_open_flag(deps.domain.llm_extraction_spec(), settings)
extractor = DomainLlmExtractor(client, spec)
...
deps.compiler.apply_extracted_claims(
    source_id,
    extracted,
    min_confidence=settings.extract_min_confidence,
    open_predicates=settings.extract_open_predicates,
)
```

`compiler/intersect.py` `extract_llm_claims_from_text`:

```python
from compiler.spec_utils import apply_open_flag
...
extractor = DomainLlmExtractor(llm_client, apply_open_flag(domain.llm_extraction_spec(), settings))
```

If sync `ingest` → `apply_extracted_claims` path exists for hybrid candidates, pass `open_predicates=resolved_settings.extract_open_predicates` there too (read `ingest` body and mirror enrichment).

- [ ] **Step 4: Run related tests**

Run:

```bash
pytest tests/test_hybrid_extraction_api.py tests/test_enrichment_runner.py tests/test_intersect.py tests/test_compiler_apply_extracted.py tests/test_domain_llm_extractor.py tests/test_extraction_settings.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add compiler/spec_utils.py compiler/enrichment.py compiler/intersect.py compiler/service.py tests/test_hybrid_extraction_api.py tests/test_enrichment_runner.py
git commit -m "feat: wire open predicate settings through enrich and LLM extract"
```

---

### Task 5: Regression sweep + README/.env note

**Files:**
- Modify: `README.md` (env table row only if present for extract_* vars)
- Modify: user `.env` is **out of scope** (do not commit secrets); document in `.env.example` only (Task 1)

- [ ] **Step 1: Run broader regression**

Run:

```bash
pytest tests/test_hybrid_extraction_api.py tests/test_enrichment_runner.py tests/test_compiler_apply_extracted.py tests/test_domain_llm_extractor.py tests/test_extraction_settings.py tests/test_domain_extraction_specs.py tests/test_intersect.py -q
```

Expected: PASS

- [ ] **Step 2: If README lists `AKOS_EXTRACT_*`, add one row for open predicates**

- [ ] **Step 3: Commit docs if changed**

```bash
git add README.md
git commit -m "docs: document AKOS_EXTRACT_OPEN_PREDICATES"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| `AKOS_EXTRACT_OPEN_PREDICATES` default true | Task 1 |
| Prompt suggested + allow novel | Task 2 |
| Lazy register + active write | Task 3 |
| Enrichment / LLM extract wiring | Task 4 |
| Closed mode regression | Task 3–4 |
| Quality gates unchanged | Task 3 (existing tests) |
| Rule path unchanged | no change / Task 5 regression |

## Placeholder scan

No TBD / “similar to Task N” without full code. Commands and expected outcomes are explicit.
