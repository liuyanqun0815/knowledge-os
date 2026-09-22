from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from akos.interfaces.api.admin_api.schemas import ZipUploadItemResponse
from infra.doc_extract import EXTRACTABLE_UPLOAD_SUFFIXES, materialize_markdown_for_ingest
from infra.upload_utils import relative_path_from_kb_root, source_id_from_relative_path
from akos.domain.models.knowledge import Source

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
    subject_bind_mode: str | None = None,
) -> None:
    from akos.application.ingest.chunk_enrichment import enrich_chunks
    from akos.application.ingest.enrichment import enrich_source, ingest_graph_extracts_llm_claims
    from akos.application.ingest.subject_bind import subject_bind_mode_override

    source_id = source_id_for_upload(kb_dir, original)
    _LOG.info("上传任务 开始 kb=%s source=%s file=%s", kb_id, source_id, original.name)
    try:
        deps.knowledge.update_source_status(source_id, "running")
        ingest_path = materialize_markdown_for_ingest(original)
        with subject_bind_mode_override(subject_bind_mode):
            report = orchestrator.ingest(
                str(ingest_path),
                source_type,
                replaces_source_id=replaces_source_id,
            )
            source_id = report.source_id
            if ingest_graph_extracts_llm_claims(settings, deps):
                deps.knowledge.update_source_status(source_id, "succeeded")
                _LOG.info(
                    "上传任务 ingest 完成（compile 已 LLM 抽 Claim，跳过 enrich_source）source=%s claims=%s",
                    source_id,
                    report.claims_created,
                )
            else:
                _LOG.info("上传任务 ingest 完成，进入 enrich_source 补抽 source=%s", source_id)
                enrich_source(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
    except Exception as exc:
        _LOG.exception("上传任务 失败 kb=%s source=%s: %s", kb_id, source_id, exc)
        try:
            deps.knowledge.update_source_status(source_id, "failed")
        except Exception:
            _LOG.exception("标记 source 失败状态出错 source=%s", source_id)
        return

    if (
        getattr(settings, "chunk_llm_enrich", False)
        or getattr(settings, "topic_cluster", False)
        or getattr(settings, "wiki_compile", False)
    ):
        _LOG.info("上传任务 后台 enrich_chunks / Wiki source=%s", source_id)
        try:
            enrich_chunks(kb_id=kb_id, source_id=source_id, deps=deps, settings=settings)
        except Exception as exc:
            # ingest 已成功，不因 enrich 失败把 source 标为 failed
            _LOG.exception(
                "上传任务 enrich_chunks 失败（source 保持 succeeded）kb=%s source=%s: %s",
                kb_id,
                source_id,
                exc,
            )
    else:
        _LOG.info("上传任务 结束 source=%s（未启用 chunk/wiki 后台 enrich）", source_id)
