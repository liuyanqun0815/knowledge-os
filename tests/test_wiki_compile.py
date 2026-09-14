from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source, SourceChunk, TopicCluster
from wiki.paths import compile_wiki_root


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
        summary=text[:20],
        text=text,
        start=0,
        end=len(text),
        topics=topics,
        status="active",
        created_at=_now(),
    )


def _claim(claim_id: str, *, source_ids: list[str]) -> Claim:
    return Claim(
        id=claim_id,
        family_id=f"fam-{claim_id}",
        version=1,
        subject="退款",
        predicate="时效",
        object="7天",
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=_now(),
        valid_to=None,
        source_ids=source_ids,
    )


def test_compile_topics_two_sources_share_topic_file(tmp_path: Path):
    from wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source("src-a", "policy_a.md"))
    knowledge.save_source(_source("src-b", "policy_b.md"))
    knowledge.save_chunks(
        "src-a",
        [_chunk("c-a", "src-a", 0, topics=["退款政策"], text="A 文档退款说明")],
    )
    knowledge.save_chunks(
        "src-b",
        [_chunk("c-b", "src-b", 0, topics=["退款政策"], text="B 文档退款说明")],
    )
    knowledge.append_claim(_claim("claim-a", source_ids=["src-a"]))
    knowledge.append_claim(_claim("claim-b", source_ids=["src-b"]))

    settings = Settings(
        wiki_compile=True,
        wiki_compile_llm=False,
        wiki_hierarchy=False,
        data_root=str(tmp_path),
    )

    # First source alone
    knowledge.save_topic_clusters(
        [
            TopicCluster(
                id="t1",
                knowledge_base_id="kb1",
                name="退款政策",
                aliases=[],
                chunk_ids=["c-a"],
                claim_ids=["claim-a"],
                source_ids=["src-a"],
                summary="退款相关",
                status="active",
                content_hash="h1",
                updated_at=_now(),
            )
        ]
    )
    report_a = compile_topics_for_source(knowledge, "kb1", "src-a", str(tmp_path), settings, graph=None)
    assert report_a.pages_written >= 1
    assert "退款政策" in report_a.topics

    wiki_root = compile_wiki_root(tmp_path, "kb1")
    topic_path = wiki_root / "topic-退款政策.md"
    assert topic_path.is_file()
    body_a = topic_path.read_text(encoding="utf-8")
    assert "## 摘要" in body_a
    assert "## Chunks" in body_a or "## 相关 Chunk" in body_a
    assert "## Claims" in body_a
    assert "## 相关原文" in body_a
    assert "## 相关实体" in body_a
    assert "## 相关主题" in body_a
    assert "[[source-src-a|policy_a.md]]" in body_a
    assert "[[退款|退款]]" in body_a
    assert "[[7天|7天]]" in body_a

    # Second source joins the same topic
    knowledge.save_topic_clusters(
        [
            TopicCluster(
                id="t1",
                knowledge_base_id="kb1",
                name="退款政策",
                aliases=[],
                chunk_ids=["c-a", "c-b"],
                claim_ids=["claim-a", "claim-b"],
                source_ids=["src-a", "src-b"],
                summary="退款相关",
                status="active",
                content_hash="h2",
                updated_at=_now(),
            )
        ]
    )
    report_b = compile_topics_for_source(knowledge, "kb1", "src-b", str(tmp_path), settings, graph=None)
    assert report_b.pages_written >= 1

    body_b = topic_path.read_text(encoding="utf-8")
    assert "[[source-src-a|policy_a.md]]" in body_b
    assert "[[source-src-b|policy_b.md]]" in body_b

    index_body = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "## 主题" in index_body
    assert "[[topic-退款政策|退款政策]]" in index_body

    from wiki.meta import load_pages_meta

    meta = load_pages_meta(wiki_root)
    page = meta.get("topic-退款政策")
    assert page is not None
    assert page.kind == "topic"
    assert set(page.source_ids) == {"src-a", "src-b"}
