# Async Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every admin source upload return `202` after disk save + `Source(pending)` registration, and run extract/ingest/enrich in `BackgroundTasks` so other API requests are not blocked.

**Architecture:** Request path only validates, writes bytes, pre-registers sources, and schedules work. New `admin_api/upload_jobs.py` owns `pending→running→materialize→ingest→enrich` (or `failed`). Lifespan resumes `pending`/`running` like existing `enriching`. Frontend treats `202` as success, shows “已接收…后台编译中”, and short-polls `listSources`.

**Tech Stack:** FastAPI `BackgroundTasks`, existing `orchestrator.ingest`, `infra.doc_extract.materialize_markdown_for_ingest`, React SourcesPage + Vitest/pytest.

## Global Constraints

- All uploads async: single / ZIP / upload-tree; suffixes `.md` `.txt` `.pdf` `.docx` `.doc`
- Success HTTP status: **202**; validation/save failures remain **4xx**
- Response: `SourceUploadResponse` + `accepted_async: true`; claim counters start at 0
- No Celery/Redis; process-local `BackgroundTasks` only
- No new `/uploads/{job_id}` API; poll `GET .../sources`
- `source_id` must match `LocalFileStore` id derived from the **ingest path** (sibling `.md` for extractables)
- Extract/OCR/ingest failures after accept → `source.status=failed`, not HTTP 4xx
- Do not change Ask / Claim retrieval semantics
- Follow black (120), PEP8, no `from module import *`

---

## File Map

| File | Responsibility |
|------|----------------|
| `admin_api/upload_jobs.py` | Pending registration helpers + background process/resume |
| `admin_api/schemas.py` | `accepted_async` on `SourceUploadResponse` |
| `admin_api/routes_sources.py` | Accept-only upload paths; schedule jobs; return 202 |
| `app/main.py` | Resume `pending` / `running` on lifespan |
| `web/src/api/types.ts` | `accepted_async`; widen `compile_status` |
| `web/src/pages/SourcesPage.tsx` | Async success copy + short polling |
| `web/src/pages/SourcesPage.test.tsx` | Assert async UX |
| `web/src/components/SourceFileBrowser.tsx` | Status labels for enriching/ready/failed |
| `tests/test_upload_jobs.py` | Unit tests for id/path + process failure |
| `tests/test_upload_resume.py` | Lifespan/resume pending |
| `tests/test_source_upload_zip.py` (and related) | Expect 202 + async fields |

---

### Task 1: Upload job helpers (id path + pending register)

**Files:**
- Create: `admin_api/upload_jobs.py`
- Test: `tests/test_upload_jobs.py`

**Interfaces:**
- Produces:
  - `ingest_path_for_upload(original: Path) -> Path`
  - `source_id_for_upload(kb_dir: Path, original: Path) -> str`
  - `register_pending_source(*, knowledge, kb_dir: Path, original: Path, source_type: str, replaces_source_id: str | None = None) -> Source`
  - `pending_item_response(kb_dir: Path, original: Path, source_id: str) -> ZipUploadItemResponse`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_upload_jobs.py
from pathlib import Path

from knowledge.memory_repo import InMemoryKnowledge


def test_ingest_path_for_extractable(tmp_path: Path):
    from admin_api.upload_jobs import ingest_path_for_upload

    assert ingest_path_for_upload(tmp_path / "a.pdf") == tmp_path / "a.md"
    assert ingest_path_for_upload(tmp_path / "b.docx") == tmp_path / "b.md"
    assert ingest_path_for_upload(tmp_path / "c.md") == tmp_path / "c.md"


def test_source_id_matches_nested_md_stem(tmp_path: Path):
    from admin_api.upload_jobs import source_id_for_upload

    original = tmp_path / "policies" / "refund.pdf"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"%PDF")
    assert source_id_for_upload(tmp_path, original) == "policies__refund"


def test_register_pending_source(tmp_path: Path):
    from admin_api.upload_jobs import register_pending_source

    knowledge = InMemoryKnowledge()
    original = tmp_path / "guide.md"
    original.write_text("七天无理由", encoding="utf-8")
    source = register_pending_source(
        knowledge=knowledge,
        kb_dir=tmp_path,
        original=original,
        source_type="policy",
    )
    assert source.status == "pending"
    assert knowledge.get_source(source.id) is not None
    assert source.id == "guide"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_upload_jobs.py -q --tb=short`  
Expected: FAIL (module / symbols missing)

- [ ] **Step 3: Implement helpers**

```python
# admin_api/upload_jobs.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from admin_api.schemas import ZipUploadItemResponse
from infra.doc_extract import EXTRACTABLE_UPLOAD_SUFFIXES
from infra.upload_utils import relative_path_from_kb_root, source_id_from_relative_path
from knowledge.models import Source

_LOG = logging.getLogger(__name__)


def ingest_path_for_upload(original: Path) -> Path:
    if original.suffix.lower() in EXTRACTABLE_UPLOAD_SUFFIXES:
        return original.with_suffix(".md")
    return original


def source_id_for_upload(kb_dir: Path, original: Path) -> str:
    ingest_path = ingest_path_for_upload(original)
    relative = relative_path_from_kb_root(ingest_path, kb_dir)
    return source_id_from_relative_path(relative)


def register_pending_source(
    *,
    knowledge,
    kb_dir: Path,
    original: Path,
    source_type: str,
    replaces_source_id: str | None = None,
) -> Source:
    source_id = source_id_for_upload(kb_dir, original)
    source = Source(
        id=source_id,
        title=ingest_path_for_upload(original).name,
        type=source_type,
        uri=f"file://{original.resolve()}",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="pending",
        replaces_source_id=replaces_source_id,
    )
    return knowledge.save_source(source)


def pending_item_response(kb_dir: Path, original: Path, source_id: str) -> ZipUploadItemResponse:
    ingest_path = ingest_path_for_upload(original)
    try:
        rel = relative_path_from_kb_root(ingest_path, kb_dir)
        relative_path = rel.as_posix()
        directory = f"/{rel.parent.as_posix()}" if rel.parent.parts else "/"
    except ValueError:
        relative_path = ingest_path.name
        directory = "/"
    return ZipUploadItemResponse(
        source_id=source_id,
        path=str(ingest_path),
        claims_created=0,
        entities_upserted=0,
        evidence_links=0,
        quarantined=0,
        errors=[],
        relative_path=relative_path,
        directory=directory,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_upload_jobs.py -q --tb=short`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add admin_api/upload_jobs.py tests/test_upload_jobs.py
git commit -m "feat: add pending source helpers for async upload"
```

---

### Task 2: Background process_uploaded_source

**Files:**
- Modify: `admin_api/upload_jobs.py`
- Modify: `tests/test_upload_jobs.py`

**Interfaces:**
- Consumes: Task 1 helpers; `materialize_markdown_for_ingest`; `orchestrator.ingest`; `enrich_source` / `enrich_chunks`
- Produces:
  - `process_uploaded_source(*, kb_id: str, kb_dir: Path, original: Path, source_type: str, deps, settings, orchestrator, replaces_source_id: str | None = None) -> None`

- [ ] **Step 1: Write failing tests**

```python
from knowledge.errors import DomainError
from knowledge.memory_repo import InMemoryKnowledge


def test_process_marks_failed_when_extract_empty(tmp_path, monkeypatch):
    from admin_api import upload_jobs

    knowledge = InMemoryKnowledge()
    original = tmp_path / "empty.pdf"
    original.write_bytes(b"%PDF")
    source = upload_jobs.register_pending_source(
        knowledge=knowledge, kb_dir=tmp_path, original=original, source_type="policy"
    )

    def boom(_path):
        raise DomainError("no extractable text")

    monkeypatch.setattr(upload_jobs, "materialize_markdown_for_ingest", boom)

    class Orchestrator:
        class deps:
            knowledge = knowledge
            llm_client = type("L", (), {"is_configured": False})()

        def ingest(self, *args, **kwargs):
            raise AssertionError("ingest must not run")

    settings = type(
        "S",
        (),
        {"extract_llm": False, "chunk_llm_enrich": False, "chunk_llm_segment": False},
    )()
    upload_jobs.process_uploaded_source(
        kb_id="kb",
        kb_dir=tmp_path,
        original=original,
        source_type="policy",
        deps=Orchestrator.deps,
        settings=settings,
        orchestrator=Orchestrator(),
    )
    assert knowledge.get_source(source.id).status == "failed"


def test_process_md_reaches_succeeded_without_llm(tmp_path):
    from admin_api import upload_jobs

    knowledge = InMemoryKnowledge()
    original = tmp_path / "note.md"
    original.write_text("七天无理由适用类目为非定制商品。", encoding="utf-8")
    source = upload_jobs.register_pending_source(
        knowledge=knowledge, kb_dir=tmp_path, original=original, source_type="policy"
    )

    class Report:
        source_id = source.id
        errors = []

    class Orchestrator:
        class deps:
            knowledge = knowledge
            llm_client = type("L", (), {"is_configured": False})()

        def ingest(self, path, source_type, replaces_source_id=None):
            knowledge.update_source_status(source.id, "ready")
            knowledge.save_source_text(source.id, Path(path).read_text(encoding="utf-8"))
            return Report()

    settings = type(
        "S",
        (),
        {"extract_llm": False, "chunk_llm_enrich": False, "chunk_llm_segment": False},
    )()
    upload_jobs.process_uploaded_source(
        kb_id="kb",
        kb_dir=tmp_path,
        original=original,
        source_type="policy",
        deps=Orchestrator.deps,
        settings=settings,
        orchestrator=Orchestrator(),
    )
    assert knowledge.get_source(source.id).status == "succeeded"
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest tests/test_upload_jobs.py::test_process_marks_failed_when_extract_empty -q --tb=short`  
Expected: FAIL (`process_uploaded_source` missing)

- [ ] **Step 3: Implement process**

```python
from infra.doc_extract import materialize_markdown_for_ingest


def process_uploaded_source(
    *,
    kb_id: str,
    kb_dir: Path,
    original: Path,
    source_type: str,
    deps,
    settings,
    orchestrator,
    replaces_source_id: str | None = None,
) -> None:
    from compiler.chunk_enrichment import enrich_chunks
    from compiler.enrichment import enrich_source

    source_id = source_id_for_upload(kb_dir, original)
    try:
        deps.knowledge.update_source_status(source_id, "running")
        ingest_path = materialize_markdown_for_ingest(original)
        report = orchestrator.ingest(
            str(ingest_path),
            source_type,
            replaces_source_id=replaces_source_id,
        )
        source_id = report.source_id
        enrich_source(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
        if (settings.chunk_llm_enrich or settings.chunk_llm_segment) and deps.llm_client.is_configured:
            enrich_chunks(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
    except Exception as exc:
        _LOG.exception("async upload failed kb=%s source=%s: %s", kb_id, source_id, exc)
        try:
            deps.knowledge.update_source_status(source_id, "failed")
        except Exception:
            _LOG.exception("failed to mark source failed: %s", source_id)
```

Notes:
- Run enrich **inline** in the worker (shared with resume); do not nest another BackgroundTasks layer here.
- `enrich_source` already sets `succeeded` when LLM is off.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_upload_jobs.py -q --tb=short`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add admin_api/upload_jobs.py tests/test_upload_jobs.py
git commit -m "feat: process async uploads in background job"
```

---

### Task 3: Schema + routes return 202

**Files:**
- Modify: `admin_api/schemas.py`
- Modify: `admin_api/routes_sources.py`
- Modify: `tests/test_source_upload_zip.py`
- Modify: other upload tests asserting HTTP 200

**Interfaces:**
- Consumes: `register_pending_source`, `pending_item_response`, `process_uploaded_source`
- Produces: upload endpoints `status_code=202`, `accepted_async=True`

- [ ] **Step 1: Add API test**

```python
def test_upload_md_returns_202_accepted_async(client, tmp_path):
    kb_id = "async-md-kb"
    response = client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload",
        files={"file": ("note.md", "# hi\n\n七天无理由适用类目为非定制商品。\n".encode(), "text/markdown")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["accepted_async"] is True
    assert body["results"][0]["claims_created"] == 0
    source_id = body["results"][0]["source_id"]

    sources = client.get(f"/admin/knowledge-bases/{kb_id}/sources")
    assert sources.status_code == 200
    statuses = {item["id"]: item["status"] for item in sources.json()}
    assert statuses[source_id] != "pending"
```

Also cover: bad suffix → 400; background extract failure → HTTP 202 then `status=failed`.

- [ ] **Step 2: Run — expect fail**

Run: `pytest tests/test_source_upload_zip.py::test_upload_md_returns_202_accepted_async -q --tb=short`

- [ ] **Step 3: Schema field**

```python
class SourceUploadResponse(BaseModel):
    upload_mode: str
    files_total: int
    files_ingested: int
    files_skipped: int
    results: list[ZipUploadItemResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    ingest_summary: str | None = None
    accepted_async: bool = False
```

- [ ] **Step 4: Wire routes**

```python
def _schedule_upload_processing(
    kb_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    kb_dir: Path,
    originals: list[Path],
    source_type: str,
    replaces_source_id: str | None = None,
) -> list[ZipUploadItemResponse]:
    orchestrator = build_orchestrator_for_request(kb_id, request)
    settings = request.app.state.settings
    results: list[ZipUploadItemResponse] = []
    single = len(originals) == 1
    for original in originals:
        source = register_pending_source(
            knowledge=orchestrator.deps.knowledge,
            kb_dir=kb_dir,
            original=original,
            source_type=source_type,
            replaces_source_id=replaces_source_id if single else None,
        )
        results.append(pending_item_response(kb_dir, original, source.id))
        background_tasks.add_task(
            process_uploaded_source,
            kb_id=kb_id,
            kb_dir=kb_dir,
            original=original,
            source_type=source_type,
            deps=orchestrator.deps,
            settings=settings,
            orchestrator=orchestrator,
            replaces_source_id=replaces_source_id if single else None,
        )
    return results
```

- Save files / unzip as today (no ingest in-request).
- Return `SourceUploadResponse(accepted_async=True, files_ingested=0, ingest_summary="已接收，后台编译中", ...)`.
- Decorators: `@router.post(..., response_model=SourceUploadResponse, status_code=202)` on upload, upload-tree, upload-zip.
- Remove in-request `_ingest_saved_file` and upload-path `_schedule_enrichment` (enrich inside job).

- [ ] **Step 5: Fix tests asserting upload `200` → `202`**

Search `sources/upload` in `tests/` and update. Revisit `test_upload_ingest_summary` — summary is now the accept message; claim deltas via later `GET` if still required.

- [ ] **Step 6: Run suites**

Run:  
`pytest tests/test_source_upload_zip.py tests/test_source_tree_ops.py tests/test_upload_jobs.py tests/test_upload_ingest_summary.py -q --tb=short`  
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add admin_api/schemas.py admin_api/routes_sources.py tests/
git commit -m "feat: accept all source uploads asynchronously with 202"
```

---

### Task 4: Lifespan resume pending/running

**Files:**
- Modify: `admin_api/upload_jobs.py`
- Modify: `app/main.py`
- Test: `tests/test_upload_resume.py`

**Interfaces:**
- Produces: `resume_incomplete_uploads(app) -> None`
- Also keep existing enriching resume (fold into one helper or call both from lifespan)

- [ ] **Step 1: Failing test**

```python
def test_resume_processes_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)

    from app.main import create_app
    from infra.bootstrap import build_orchestrator_for_kb
    from admin_api.upload_jobs import register_pending_source, resume_incomplete_uploads

    app = create_app(data_root=str(tmp_path))
    kb_id = "kb1"
    orch = build_orchestrator_for_kb(kb_id)
    app.state.orchestrator_cache[kb_id] = orch
    kb_dir = tmp_path / kb_id
    kb_dir.mkdir(parents=True)
    original = kb_dir / "x.md"
    original.write_text("七天无理由适用类目为非定制商品。", encoding="utf-8")
    register_pending_source(
        knowledge=orch.deps.knowledge,
        kb_dir=kb_dir,
        original=original,
        source_type="policy",
    )
    resume_incomplete_uploads(app)
    src = orch.deps.knowledge.get_source("x")
    assert src is not None
    assert src.status != "pending"
```

Adjust `build_orchestrator_for_kb` call to match `infra/bootstrap.py` (pass settings if required).

- [ ] **Step 2: Implement**

```python
def _path_from_file_uri(uri: str) -> Path | None:
    if not uri.startswith("file://"):
        return None
    raw = uri.removeprefix("file://")
    if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
        raw = raw[1:]
    return Path(raw)


def resume_incomplete_uploads(app) -> None:
    settings = app.state.settings
    cache = getattr(app.state, "orchestrator_cache", {})
    for kb_id, orchestrator in list(cache.items()):
        kb_dir = Path(settings.data_root) / kb_id
        for source in orchestrator.deps.knowledge.list_sources():
            if source.status not in {"pending", "running"}:
                continue
            original = _path_from_file_uri(source.uri)
            if original is None or not original.is_file():
                orchestrator.deps.knowledge.update_source_status(source.id, "failed")
                continue
            process_uploaded_source(
                kb_id=kb_id,
                kb_dir=kb_dir,
                original=original,
                source_type=source.type,
                deps=orchestrator.deps,
                settings=settings,
                orchestrator=orchestrator,
                replaces_source_id=source.replaces_source_id,
            )
```

In `app/main.py`, after loading orchestrators (reuse `_load_orchestrators_for_resume` so PG KBs are populated), call `resume_incomplete_uploads` in the same `to_thread` job as enriching resume, or sequentially in one function `_resume_background_source_jobs`.

- [ ] **Step 3: Run**

Run: `pytest tests/test_upload_resume.py -q --tb=short`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/main.py admin_api/upload_jobs.py tests/test_upload_resume.py
git commit -m "feat: resume pending uploads on app startup"
```

---

### Task 5: Frontend accept UX + polling

**Files:**
- Modify: `web/src/api/types.ts`
- Modify: `web/src/pages/SourcesPage.tsx`
- Modify: `web/src/pages/SourcesPage.test.tsx`
- Modify: `web/src/components/SourceFileBrowser.tsx`

**Interfaces:**
- Consumes: `accepted_async` on upload JSON
- Produces: banner + background poll of `listSources`

- [ ] **Step 1: Types + labels**

```typescript
compile_status:
  | "pending"
  | "running"
  | "enriching"
  | "succeeded"
  | "succeeded_partial"
  | "failed"
  | "ready";

// SourceUploadResponse
accepted_async?: boolean;
ingest_summary?: string | null;
```

```typescript
const STATUS_LABELS: Record<string, string> = {
  pending: "等待编译",
  running: "编译中",
  enriching: "LLM 补抽中",
  ready: "已完成",
  succeeded: "已完成",
  succeeded_partial: "部分完成",
  failed: "编译失败",
};
```

- [ ] **Step 2: SourcesPage — after upload**

```typescript
const result = await uploadSource(/* or uploadTree */);
setSelectedFile(null);
setSelectedTreeEntries([]);
setUploadSummary(
  result.accepted_async !== false
    ? `已接收 ${result.results.length} 个文件，后台编译中`
    : formatUploadSummary(result),
);
setIsUploading(false);
void (async () => {
  const deadline = Date.now() + 180_000;
  while (Date.now() < deadline && kbId) {
    const items = await listSources(kbId);
    setSources(items);
    const busy = items.some(
      (s) =>
        s.compile_status === "pending" ||
        s.compile_status === "running" ||
        s.compile_status === "enriching",
    );
    if (!busy) return;
    await new Promise((r) => setTimeout(r, 2000));
  }
})();
```

Note: `apiFetch` already treats 202 as OK (`response.ok`).

- [ ] **Step 3: Vitest**

Mock upload → `{ accepted_async: true, results: [{ source_id: "a" }], files_total: 1, ... }`;  
`listSources` → first `[{ compile_status: "pending" }]` then `[{ compile_status: "succeeded" }]`;  
assert banner matches `/后台编译中/`.

- [ ] **Step 4: Run**

Run: `npm test -- --run src/pages/SourcesPage.test.tsx`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/api/types.ts web/src/pages/SourcesPage.tsx web/src/pages/SourcesPage.test.tsx web/src/components/SourceFileBrowser.tsx
git commit -m "feat: poll sources after async upload accept"
```

---

### Task 6: Regression sweep

- [ ] **Step 1: Run broader backend tests**

```bash
pytest tests/test_source_upload_zip.py tests/test_source_tree_ops.py tests/test_upload_jobs.py tests/test_upload_resume.py tests/test_hybrid_extraction_api.py tests/test_evolution_api.py tests/test_admin_kb_api.py tests/test_doc_extract.py -q --tb=line
```

Fix remaining upload `200` assertions.

- [ ] **Step 2: Commit if needed**

```bash
git add tests/
git commit -m "test: align upload suites with async 202 accept"
```

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| All uploads async | 3 |
| 202 + `accepted_async` | 3, 5 |
| pending + matching `source_id` | 1 |
| Background materialize + ingest + enrich | 2 |
| failed after accept | 2, 3 |
| Poll `GET sources` (no job API) | 5 |
| Resume pending/running | 4 |
| No Celery | constraint |
| Spec §8 tests | 1–5 |

**Placeholder scan:** none.  
**Signature consistency:** `process_uploaded_source(*, kb_id, kb_dir, original, source_type, deps, settings, orchestrator, replaces_source_id=None)` across Tasks 2–4.
