"""Hierarchical wiki compile: hub folders + snippet fold."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim, Source, SourceChunk, TopicCluster
from akos.application.wiki.paths import compile_wiki_root


class FakeLlmClient:
    is_configured = True

    def __init__(self, response: str = "[]") -> None:
        self.response = response

    def chat_completions(self, messages, *, temperature=0.0, timeout=60.0) -> str:
        return self.response


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _source(source_id: str, title: str) -> Source:
    return Source(
        id=source_id,
        title=title,
        type="md",
        uri=f"file://{source_id}",
        version="1",
        created_at=_now(),
        status="active",
    )


def _chunk(chunk_id: str, source_id: str, index: int, *, topics: list[str], text: str) -> SourceChunk:
    return SourceChunk(
        id=chunk_id,
        source_id=source_id,
        chunk_index=index,
        title=f"chunk-{index}",
        summary=text[:40],
        text=text,
        start=0,
        end=len(text),
        topics=topics,
        status="active",
        created_at=_now(),
    )


def _claim(claim_id: str, *, subject: str, obj: str, source_ids: list[str]) -> Claim:
    return Claim(
        id=claim_id,
        family_id=f"fam-{claim_id}",
        version=1,
        subject=subject,
        predicate="提及",
        object=obj,
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=_now(),
        valid_to=None,
        source_ids=source_ids,
    )


def _cluster(
    cid: str,
    name: str,
    *,
    chunk_ids: list[str],
    claim_ids: list[str],
    source_ids: list[str],
    summary: str = "",
) -> TopicCluster:
    return TopicCluster(
        id=cid,
        knowledge_base_id="kb1",
        name=name,
        aliases=[],
        chunk_ids=chunk_ids,
        claim_ids=claim_ids,
        source_ids=source_ids,
        summary=summary,
        status="active",
        content_hash=cid,
        updated_at=_now(),
    )


def test_compile_hierarchy_folds_snippets_under_hub(tmp_path: Path) -> None:
    from akos.application.wiki.compile import _compile_hierarchy_for_source

    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("src-1", "cs.md"))
    knowledge.save_chunks(
        "src-1",
        [
            _chunk("c-unk", "src-1", 0, topics=["不知道"], text="不要说不知道这类禁用词"),
            _chunk("c-comm", "src-1", 1, topics=["客服沟通"], text="沟通时保持礼貌与清晰"),
        ],
    )
    knowledge.append_claim(_claim("cl-unk", subject="客服", obj="禁用不知道", source_ids=["src-1"]))
    knowledge.append_claim(_claim("cl-comm", subject="客服", obj="礼貌沟通", source_ids=["src-1"]))
    knowledge.save_topic_clusters(
        [
            _cluster(
                "t-unk",
                "不知道",
                chunk_ids=["c-unk"],
                claim_ids=["cl-unk"],
                source_ids=["src-1"],
                summary="禁用短语",
            ),
            _cluster(
                "t-comm",
                "客服沟通",
                chunk_ids=["c-comm"],
                claim_ids=["cl-comm"],
                source_ids=["src-1"],
                summary="沟通规范摘要",
            ),
        ]
    )

    settings = Settings(
        wiki_compile=True,
        wiki_migrate_flat=True,
        wiki_max_related=12,
        data_root=str(tmp_path),
        _env_file=None,
    )
    wiki_root = compile_wiki_root(tmp_path, "kb1")
    wiki_root.mkdir(parents=True, exist_ok=True)
    report = _compile_hierarchy_for_source(
        knowledge, "kb1", "src-1", wiki_root, settings, llm_client=FakeLlmClient()
    )
    assert report.pages_written >= 1

    hub_dir = wiki_root / "客服话术"
    assert (hub_dir / "_index.md").is_file()
    assert (hub_dir / "沟通规范.md").is_file()
    assert (hub_dir / "禁用表达.md").is_file()
    assert not (wiki_root / "topic-不知道.md").exists()
    assert not (wiki_root / "topic-客服沟通.md").exists()

    banned_body = (hub_dir / "禁用表达.md").read_text(encoding="utf-8")
    assert "禁用不知道" in banned_body or "不要说不知道" in banned_body

    comm_body = (hub_dir / "沟通规范.md").read_text(encoding="utf-8")
    assert "礼貌沟通" in comm_body or "沟通时保持礼貌" in comm_body
    assert "[[客服话术/" in comm_body  # related / hub path links
    assert "topic-" not in comm_body

    index_body = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "客服话术" in index_body
    assert "沟通规范" in index_body or "禁用表达" in index_body

    from akos.application.wiki.meta import load_pages_meta

    meta = load_pages_meta(wiki_root)
    leaf_meta = meta.get("客服话术/沟通规范") or meta.get("客服话术/沟通规范.md")
    assert leaf_meta is not None
    assert getattr(leaf_meta, "hub", None) == "客服话术"
    assert getattr(leaf_meta, "role", None) in {"leaf", "topic", "hub"}


def test_compile_hierarchy_migrates_flat_topic_files(tmp_path: Path) -> None:
    from akos.application.wiki.compile import _compile_hierarchy_for_source

    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("src-1", "cs.md"))
    knowledge.save_chunks(
        "src-1",
        [_chunk("c-comm", "src-1", 0, topics=["客服沟通"], text="沟通规范内容")],
    )
    knowledge.save_topic_clusters(
        [
            _cluster(
                "t-comm",
                "客服沟通",
                chunk_ids=["c-comm"],
                claim_ids=[],
                source_ids=["src-1"],
                summary="沟通",
            ),
        ]
    )

    wiki_root = compile_wiki_root(tmp_path, "kb1")
    wiki_root.mkdir(parents=True, exist_ok=True)
    stale = wiki_root / "topic-客服沟通.md"
    stale.write_text("# stale flat\n", encoding="utf-8")

    settings = Settings(
        wiki_compile=True,
        wiki_migrate_flat=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    _compile_hierarchy_for_source(
        knowledge, "kb1", "src-1", wiki_root, settings, llm_client=FakeLlmClient()
    )
    assert not stale.exists()
    assert (wiki_root / "客服话术" / "沟通规范.md").is_file()


def test_compile_flat_topic_pages(tmp_path: Path) -> None:
    from akos.application.wiki.compile import _compile_flat_for_source

    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("src-1", "a.md"))
    knowledge.save_chunks(
        "src-1",
        [_chunk("c1", "src-1", 0, topics=["退款政策"], text="退款说明")],
    )
    knowledge.save_topic_clusters(
        [
            _cluster(
                "t1",
                "退款政策",
                chunk_ids=["c1"],
                claim_ids=[],
                source_ids=["src-1"],
                summary="退款",
            ),
        ]
    )
    settings = Settings(
        wiki_compile=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    wiki_root = compile_wiki_root(tmp_path, "kb1")
    wiki_root.mkdir(parents=True, exist_ok=True)
    _compile_flat_for_source(knowledge, "kb1", "src-1", wiki_root, settings, llm_client=FakeLlmClient())
    assert (wiki_root / "topic-退款政策.md").is_file()
