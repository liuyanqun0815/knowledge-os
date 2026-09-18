# AKOS Hexagonal Phase 6c — Collapse low-value root packages

> **For agentic workers:** No shims. Checkbox steps.

**Goal:** Remove root packages that no longer deserve independence: `agents/`, `verification/`, `ontology/`, `knowledge/` (lint/topic only).

**Map**

| From | To |
|------|----|
| `agents/retriever_agent` | `akos.application.ask.retrieve` |
| `agents/memory_agent` | `akos.application.ask.memory_ops` |
| `agents/verification_agent` + `verification/service` | `akos.application.ask.verification` |
| `agents/{compiler,evolution,research}_agent` | **delete** (unused / trivial) |
| `ontology/registry.py` | `akos.adapters.ontology.memory` |
| `knowledge/lint*.py` | `akos.application.lint` |
| `knowledge/topic_*.py` | `akos.application.topics` |

**Then:** rewrite imports; drop packages from `pyproject`; update README/spec §9; regression + commit/push.
