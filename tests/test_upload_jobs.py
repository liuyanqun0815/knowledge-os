from pathlib import Path

from knowledge.errors import DomainError
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
        def ingest(self, *args, **kwargs):
            raise AssertionError("ingest must not run")

    Orchestrator.deps = type(
        "deps",
        (),
        {"knowledge": knowledge, "llm_client": type("L", (), {"is_configured": False})()},
    )()

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
        def ingest(self, path, source_type, replaces_source_id=None):
            knowledge.update_source_status(source.id, "ready")
            knowledge.save_source_text(source.id, Path(path).read_text(encoding="utf-8"))
            return Report()

    Orchestrator.deps = type(
        "deps",
        (),
        {"knowledge": knowledge, "llm_client": type("L", (), {"is_configured": False})()},
    )()

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
