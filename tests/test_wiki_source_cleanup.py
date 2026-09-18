from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from akos.interfaces.api.admin_api.source_cleanup import purge_source_side_effects, sole_source_claims
from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim, Source
from akos.application.wiki.meta import WikiPageMeta, load_pages_meta, save_pages_meta
from akos.application.wiki.paths import compile_wiki_root


def _write_sole_wiki(tmp_path: Path, kb_id: str, source_id: str) -> Path:
    wiki_root = compile_wiki_root(tmp_path, kb_id)
    page_rel = "未分类/贷款产品合集.md"
    page_path = wiki_root / page_rel
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text("# 贷款产品合集\n\n个人信用贷款定义。\n", encoding="utf-8")
    (wiki_root / "index.md").write_text(
        "## 主题\n\n### 未分类\n- [[未分类/贷款产品合集|贷款产品合集]]\n",
        encoding="utf-8",
    )
    save_pages_meta(
        wiki_root,
        {
            "未分类/贷款产品合集": WikiPageMeta(
                path=page_rel,
                title="贷款产品合集",
                kind="source_page",
                content_hash="hash-1",
                source_ids=[source_id],
                summary="贷款产品合集",
            )
        },
    )
    return wiki_root


def test_purge_source_side_effects_deletes_sole_source_wiki(tmp_path: Path):
    kb_id = "kb-wiki-cleanup"
    knowledge = InMemoryKnowledge()
    knowledge.save_source(
        Source(
            id="s1",
            title="贷款产品",
            type="md",
            uri="file://s1",
            version="1",
            created_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
            status="ready",
        )
    )
    knowledge.append_claim(
        Claim(
            id="c1",
            family_id="f1",
            version=1,
            subject="个人信用贷款",
            predicate="定义",
            object="无需抵押",
            subject_type="Product",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            source_ids=["s1"],
        )
    )
    wiki_root = _write_sole_wiki(tmp_path, kb_id, "s1")
    assert (wiki_root / "未分类/贷款产品合集.md").is_file()

    settings = Settings(
        _env_file=None,
        data_root=str(tmp_path),
        wiki_compile=True,
        wiki_compile_llm=False,
        topic_cluster=False,
    )
    sole = sole_source_claims(knowledge, "s1")
    knowledge.delete_source("s1")
    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=SimpleNamespace(),
        knowledge_base_id=kb_id,
        chunk_retrieval=SimpleNamespace(remove_source=lambda _sid: None),
        retrieval=SimpleNamespace(remove_claim=lambda _cid: None),
        wiki_retrieval=SimpleNamespace(index_wiki_root=lambda _root: None),
        llm_client=None,
    )
    purge_source_side_effects(deps, "s1", sole_claims=sole, settings=settings)

    assert not (wiki_root / "未分类/贷款产品合集.md").exists()
    assert load_pages_meta(wiki_root) == {}
    index_text = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "贷款产品合集" not in index_text


def test_purge_wiki_keeps_multi_source_page_and_strips_deleted_id(tmp_path: Path):
    from akos.application.wiki.cleanup import purge_wiki_for_deleted_source

    kb_id = "kb-wiki-multi"
    knowledge = InMemoryKnowledge()
    knowledge.save_source(
        Source(
            id="s-keep",
            title="退款政策A",
            type="md",
            uri="file://keep",
            version="1",
            created_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
            status="ready",
        )
    )
    wiki_root = compile_wiki_root(tmp_path, kb_id)
    page_rel = "topic-退款政策.md"
    page_path = wiki_root / page_rel
    page_path.parent.mkdir(parents=True, exist_ok=True)
    page_path.write_text("# 退款政策\n\n共享主题页。\n", encoding="utf-8")
    (wiki_root / "index.md").write_text("## 主题\n\n- [[topic-退款政策|退款政策]]\n", encoding="utf-8")
    save_pages_meta(
        wiki_root,
        {
            "topic-退款政策": WikiPageMeta(
                path=page_rel,
                title="退款政策",
                kind="topic",
                content_hash="hash-multi",
                source_ids=["s-gone", "s-keep"],
                summary="退款政策",
            )
        },
    )

    settings = Settings(
        _env_file=None,
        data_root=str(tmp_path),
        wiki_compile=True,
        wiki_compile_llm=False,
        wiki_hierarchy=False,
        wiki_source_plan=False,
        topic_cluster=False,
    )
    # Avoid heavy recompile: stub compile by leaving wiki_hierarchy/source_plan flat
    # but monkeypatch compile to no-op via settings that still strip ids first.
    result = purge_wiki_for_deleted_source(
        kb_id=kb_id,
        source_id="s-gone",
        knowledge=knowledge,
        data_root=tmp_path,
        settings=settings,
        wiki_retrieval=None,
    )

    meta = load_pages_meta(wiki_root)
    assert "topic-退款政策" in meta
    assert meta["topic-退款政策"].source_ids == ["s-keep"]
    assert page_path.is_file()
    assert result["deleted_pages"] == 0
    assert result["recompiled_sources"] == 1
