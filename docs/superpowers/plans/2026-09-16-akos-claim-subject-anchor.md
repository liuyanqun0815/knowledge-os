# Claim Subject Document Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve a single document-level product anchor and inject it into LLM claim extraction so `subject` is the product entity (not bare attribute words like「还款方式」).

**Architecture:** Heuristic `resolve_document_anchor(text, title)` picks 产品简称 / 产品名称 / title. `DomainLlmExtractor.extract(..., document_anchor=)` adds prompt rules and JSON `document_anchor`. `enrich_source` and `extract_llm_claims_from_text` resolve once per document and pass the anchor to every chunk.

**Tech Stack:** Python 3.11+, existing `DomainLlmExtractor` / `enrichment` / pytest; black line-length 120.

## Global Constraints

- Triple form: `subject=产品名`, `predicate=属性/关系`, `object=值` (not「产品名的还款方式」as subject)
- Full-document single anchor only (one product per doc); multi-product collections out of scope
- No hard blacklist quarantine this phase; no historical claim rewrite
- Anchor missing → still extract with prompt rules only
- Prefer 产品简称 over 产品名称 when both exist
- No star imports; black 120; TDD

---

## File Map

| File | Responsibility |
|------|----------------|
| `compiler/document_anchor.py` | `resolve_document_anchor(text, title=None) -> str \| None` |
| `compiler/domain_llm_extractor.py` | Prompt rules + `document_anchor` in extract/build_prompt |
| `compiler/enrichment.py` | Resolve anchor once; pass into each chunk extract |
| `compiler/intersect.py` | Same for ingest-time LLM path |
| `compiler/llm_extractor.py` | Forward `document_anchor` if wrapping extract |
| `domains/loan_finance/domain.py` | few_shot_hints 正反例 |
| `tests/test_document_anchor.py` | Anchor heuristics |
| `tests/test_domain_llm_extractor.py` | Prompt contains rules + anchor |

---

### Task 1: resolve_document_anchor

**Files:**
- Create: `compiler/document_anchor.py`
- Test: `tests/test_document_anchor.py`

**Interfaces:**
- Produces: `resolve_document_anchor(text: str, title: str | None = None) -> str | None`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_document_anchor.py
from compiler.document_anchor import resolve_document_anchor

SAMPLE = """
二、产品概述
产品名称
青银理财璀璨人生成就系列人民币个人理财计划（低波共享）2024 年109 期
产品简称
青银理财成就系列（低波共享）2024 年109 期
产品代码
CCCJGX24109
"""


def test_prefers_product_short_name():
    anchor = resolve_document_anchor(SAMPLE)
    assert anchor is not None
    assert "成就系列" in anchor
    assert "低波共享" in anchor


def test_falls_back_to_title_when_no_fields():
    assert resolve_document_anchor("无表格字段", title="某某理财产品说明书.md") == "某某理财产品说明书"


def test_returns_none_when_empty():
    assert resolve_document_anchor("", title=None) is None
    assert resolve_document_anchor("   ", title="  ") is None
```

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/test_document_anchor.py -q --tb=short`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# compiler/document_anchor.py
from __future__ import annotations

import re
from pathlib import Path

_SHORT = re.compile(
    r"产品简称\s*[:：]?\s*\n?\s*(?P<value>[^\n]+)",
    re.MULTILINE,
)
_FULL = re.compile(
    r"产品名称\s*[:：]?\s*\n?\s*(?P<value>[^\n]+)",
    re.MULTILINE,
)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def resolve_document_anchor(text: str, title: str | None = None) -> str | None:
    body = text or ""
    for pattern in (_SHORT, _FULL):
        match = pattern.search(body)
        if match:
            value = _clean(match.group("value"))
            if value:
                return value
    if title:
        stem = Path(title).stem if "." in title else title.strip()
        stem = _clean(stem)
        if stem:
            return stem
    return None
```

Tune regex if SAMPLE from 青银说明书 uses newline-separated labels (as in fixture above). Prefer matching both `产品简称\n值` and `产品简称：值`.

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/test_document_anchor.py -q --tb=short`

- [ ] **Step 5: Commit**

```bash
git add compiler/document_anchor.py tests/test_document_anchor.py
git commit -m "feat: resolve document product anchor from说明书 fields"
```

---

### Task 2: Prompt rules + extract(document_anchor=)

**Files:**
- Modify: `compiler/domain_llm_extractor.py`
- Modify: `tests/test_domain_llm_extractor.py` (extend existing)

**Interfaces:**
- Consumes: none from Task 1 (anchor string only)
- Produces:
  - `DomainLlmExtractor.extract(self, text: str, *, document_anchor: str | None = None) -> list[ExtractedClaim]`
  - `_build_prompt(self, text: str, *, document_anchor: str | None = None) -> str`

- [ ] **Step 1: Failing test**

```python
def test_build_prompt_includes_subject_rules_and_anchor():
    from compiler.domain_llm_extractor import DomainLlmExtractor
    from compiler.extraction_spec import LlmExtractionSpec

    class FakeClient:
        is_configured = True

        def chat_completions(self, messages, **kwargs):
            return "[]"

    extractor = DomainLlmExtractor(FakeClient(), LlmExtractionSpec(
        allowed_predicates=["还款方式"],
        entity_types=["Product"],
    ))
    prompt = extractor._build_prompt(
        "还款方式包含等额本息。",
        document_anchor="青银理财成就系列（低波共享）",
    )
    assert "还款方式" in prompt  # still in rules as banned bare subject example
    assert "青银理财成就系列（低波共享）" in prompt
    assert "document_anchor" in prompt
    assert "禁止单独使用属性词" in prompt or "属性词" in prompt
```

Adapt assertion strings to the exact Chinese rule text you add.

- [ ] **Step 2: Run — expect fail**

- [ ] **Step 3: Update `_PROMPT` rules** (append after rule 9):

```text
10. subject 必须是原文中的具体产品名、政策/规则名或主题实体；禁止单独使用属性词（如「利率」「额度」「还款方式」「收入要求」）作 subject。属性写入 predicate，取值写入 object。
11. 若配置中提供 document_anchor：本段 Claim 的 subject 应使用该锚点（或原文中与之同指的产品全称/简称），不要改用泛化属性词。
```

In `_build_prompt`, add to `configuration`:

```python
if document_anchor:
    configuration["document_anchor"] = document_anchor
```

Update `extract` signature to accept `document_anchor` and pass to `_build_prompt`.

Update `compiler/llm_extractor.py` if it overrides `extract` — forward kwargs.

- [ ] **Step 4: Run related extractor tests**

Run: `pytest tests/test_domain_llm_extractor.py tests/test_extraction_settings.py -q --tb=short`

- [ ] **Step 5: Commit**

```bash
git add compiler/domain_llm_extractor.py compiler/llm_extractor.py tests/test_domain_llm_extractor.py
git commit -m "feat: inject document_anchor into LLM claim extraction prompt"
```

---

### Task 3: Wire enrichment + intersect

**Files:**
- Modify: `compiler/enrichment.py`
- Modify: `compiler/intersect.py`
- Test: `tests/test_enrichment_runner.py` and/or new focused unit test with mocks

**Interfaces:**
- Consumes: `resolve_document_anchor`, `extract(..., document_anchor=)`

- [ ] **Step 1: Failing test (enrichment passes anchor)**

```python
def test_enrich_source_passes_document_anchor(monkeypatch):
    from compiler import enrichment

    calls = []

    class FakeExtractor:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, text, *, document_anchor=None):
            calls.append(document_anchor)
            return []

    monkeypatch.setattr(enrichment, "DomainLlmExtractor", FakeExtractor)
    monkeypatch.setattr(
        enrichment,
        "resolve_document_anchor",
        lambda text, title=None: "锚点产品",
    )
    # build minimal deps/settings/source text — follow existing test_enrichment_runner patterns
    ...
    assert calls and calls[0] == "锚点产品"
```

Reuse fixtures from `tests/test_enrichment_runner.py` rather than inventing a new deps shape. If that file already stubs extractor, extend it.

For `extract_llm_claims_from_text`:

```python
from compiler.document_anchor import resolve_document_anchor

def extract_llm_claims_from_text(...):
    extractor = DomainLlmExtractor(...)
    anchor = resolve_document_anchor(text)
    if len(text) <= settings.chunk_max_chars:
        return extractor.extract(text, document_anchor=anchor)
    ...
        for claim in extractor.extract(chunk, document_anchor=anchor):
```

In `enrich_source`:

```python
from compiler.document_anchor import resolve_document_anchor

text = deps.knowledge.get_source_text(source_id)
source = deps.knowledge.get_source(source_id)
anchor = resolve_document_anchor(text, title=getattr(source, "title", None) if source else None)
...
extracted.extend(extractor.extract(chunk, document_anchor=anchor))
```

- [ ] **Step 2–4: Implement, run**

Run: `pytest tests/test_enrichment_runner.py tests/test_hybrid_extraction_api.py tests/test_document_anchor.py tests/test_domain_llm_extractor.py -q --tb=short`

- [ ] **Step 5: Commit**

```bash
git add compiler/enrichment.py compiler/intersect.py tests/
git commit -m "feat: pass document product anchor through enrich and hybrid LLM extract"
```

---

### Task 4: loan_finance few-shot + regression

**Files:**
- Modify: `domains/loan_finance/domain.py`
- Modify: `domains/generic/domain.py` (optional short hints)
- Modify: `tests/test_domain_extraction_specs.py` or `tests/test_extraction_settings.py` if they assert empty hints

- [ ] **Step 1: Add hints**

```python
def llm_extraction_spec(self) -> LlmExtractionSpec:
    return LlmExtractionSpec(
        allowed_predicates=["适用客户", "利率_年化", "最高额度", "还款方式"],
        entity_types=["Product", "RateRule", "RiskLevel"],
        few_shot_hints=[
            "正例：subject=青银理财成就系列（低波共享），predicate=还款方式，object=等额本息、等额本金",
            "反例：subject=还款方式（禁止：属性词不可单独作 subject）",
        ],
    )
```

- [ ] **Step 2: Assert hints appear in prompt**

```python
def test_loan_finance_hints_in_prompt():
    from domains.loan_finance.domain import LoanFinanceDomain
    from compiler.domain_llm_extractor import DomainLlmExtractor
    ...
    spec = LoanFinanceDomain().llm_extraction_spec()
    extractor = DomainLlmExtractor(FakeClient(), spec)
    prompt = extractor._build_prompt("x", document_anchor="青银理财成就系列（低波共享）")
    assert "正例" in prompt or "成就系列" in prompt
```

- [ ] **Step 3: Run**

Run: `pytest tests/test_domain_extraction_specs.py tests/test_document_anchor.py tests/test_domain_llm_extractor.py -q --tb=short`

- [ ] **Step 4: Commit**

```bash
git add domains/loan_finance/domain.py domains/generic/domain.py tests/
git commit -m "feat: add loan_finance few-shot hints for product-as-subject claims"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| resolve_document_anchor 简称 > 名称 > title | 1 |
| Prompt rules 10–11 + configuration.document_anchor | 2 |
| enrich + other LLM path wire anchor | 3 |
| loan_finance few_shot | 4 |
| No multi-doc section anchor / no backfill | constraints |
| Triple form product/predicate/object | prompt + hints |

**Placeholder scan:** none.  
**Signature consistency:** `extract(text, *, document_anchor=None)` / `resolve_document_anchor(text, title=None)`.
