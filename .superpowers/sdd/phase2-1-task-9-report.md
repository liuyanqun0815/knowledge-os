# Phase 2.1 Task 9 Report: LLM config stub + corporate culture domain skeleton

**Status:** DONE  
**Date:** 2026-09-08  
**Baseline:** 69f22e7 (Task 6/7 follow-up — ask kb_id + admin token)  
**Commit:** docs: add Phase 2.1 env config and corporate culture domain skeleton

## TDD Execution

| Step | Action | Result |
|------|--------|--------|
| 1 | Test OpenAiCompatibleClient raises without key | Done |
| 2 | Test LlmExtractor skips without key; parses JSON when stubbed | Done |
| 3 | Test corporate ontology seeds + formatter + LlmExtractor wiring | Done |
| 4 | Full suite `pytest -v` | **41 passed, 19 skipped** |
| 5 | Commit + README Phase 2.1 acceptance commands | Done |

## Files Created / Modified

| File | Change |
|------|--------|
| `infra/llm.py` | `OpenAiCompatibleClient` stub; `LlmConfigError` when `AKOS_LLM_API_KEY` missing |
| `infra/settings.py` | `llm_base_url`, `llm_api_key`, `llm_model` settings |
| `compiler/llm_extractor.py` | `LlmExtractor` skeleton; corporate-only in 2.1; skip when no key |
| `domains/corporate_culture/seed.py` | Entity seeds (Value, Behavior, Policy, Department) + predicates |
| `domains/corporate_culture/formatter.py` | `format_corporate_claim` for 倡导/禁止/适用于 |
| `domains/corporate_culture/domain.py` | Register corporate ontology; `get_extractor()` → `LlmExtractor` |
| `.env.example` | `AKOS_LLM_BASE_URL`, `AKOS_LLM_API_KEY`, `AKOS_LLM_MODEL` |
| `README.md` | LLM env vars + Phase 2.1 acceptance commands |
| `tests/test_corporate_domain_skeleton.py` | Unit tests + optional LLM integration (skipif no key) |

## LLM Configuration

```text
AKOS_LLM_BASE_URL=https://api.openai.com/v1
AKOS_LLM_API_KEY=
AKOS_LLM_MODEL=gpt-4o-mini
```

Without `AKOS_LLM_API_KEY`:

- `OpenAiCompatibleClient.chat_completions()` raises `LlmConfigError` with explicit message
- `LlmExtractor.extract()` returns `[]` (corporate upload skips LLM extraction)

With key configured:

- Optional integration test: `pytest -k llm_integration`

## Corporate Culture Ontology (minimal seeds)

| Entity type | Examples |
|-------------|----------|
| Value | 诚信, 协作, 客户第一 |
| Behavior | 加班文化, 内部竞争 |
| Policy | 员工手册, 行为准则 |
| Department | 研发部, 人力资源部 |

| Predicate | Subject → Object |
|-----------|------------------|
| 倡导 | Value → Behavior / Value |
| 禁止 | Policy → Behavior |
| 适用于 | Policy → Department / Behavior |

## Example Usage

```python
from infra.llm import OpenAiCompatibleClient, LlmConfigError
from infra.settings import Settings

client = OpenAiCompatibleClient(Settings(llm_api_key=""))
try:
    client.chat_completions([{"role": "user", "content": "hi"}])
except LlmConfigError as exc:
    print(exc)  # AKOS_LLM_API_KEY is not set...

from domains.registry import load_domain
from ontology.registry import InMemoryOntology

domain = load_domain("corporate_culture")
ontology = InMemoryOntology()
domain.register_ontology(ontology)
assert ontology.resolve_entity_type("诚信") == "Value"

extractor = domain.get_extractor()
assert extractor.extract("员工手册倡导诚信。") == []  # no key → skip
```

## Phase 2.1 Acceptance Notes

- Corporate culture KB upload without LLM key: claims may be 0 (skip path); ecommerce_cs still uses RuleExtractor
- With LLM key: corporate upload can produce claims via OpenAI-compatible API
- Remaining checklist items covered by Tasks 6–8 and Task 10 (e2e compat)

## Next

Task 10: adapt phase-1 e2e to knowledge base scoped orchestrator (`test_kb_id=test-ecommerce`).
