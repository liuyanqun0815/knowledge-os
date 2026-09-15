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
