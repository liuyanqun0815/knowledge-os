from __future__ import annotations

from datetime import datetime, timezone

from akos.domain.models.knowledge import Claim, SourceChunk
from akos.application.topics.cluster import build_topic_clusters, normalize_topic_name


def _chunk(
    *,
    chunk_id: str = "c1",
    source_id: str = "s1",
    topics: list[str] | None = None,
    section_path: list[str] | None = None,
) -> SourceChunk:
    return SourceChunk(
        id=chunk_id,
        source_id=source_id,
        chunk_index=0,
        title="尺码指南",
        summary=None,
        text="示例文本",
        start=0,
        end=10,
        section_path=section_path or [],
        topics=topics or [],
        status="active",
        created_at=datetime(2026, 9, 11, tzinfo=timezone.utc),
    )


def _claim(*, claim_id: str = "cl1", subject: str = "尺码选择") -> Claim:
    return Claim(
        id=claim_id,
        family_id="f1",
        version=1,
        subject=subject,
        predicate="建议",
        object="核对尺码表",
        subject_type="Concept",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=None,
        valid_to=None,
        source_ids=["s1"],
    )


def test_normalize_applies_alias_map():
    assert normalize_topic_name("尺码表", {"尺码表": "尺码选择"}) == "尺码选择"


def test_normalize_strips_whitespace_and_punctuation():
    assert normalize_topic_name("  尺码表！  ") == "尺码选择"


def test_normalize_uses_default_aliases():
    assert normalize_topic_name("尺码指南") == "尺码选择"


def test_build_merges_aliases_and_attaches_claims():
    chunk = _chunk(topics=["尺码表"], section_path=["商品咨询", "尺码选择指南"])
    claim = _claim(subject="尺码选择")

    clusters = build_topic_clusters(
        knowledge_base_id="kb1",
        chunks=[chunk],
        claims=[claim],
    )

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.name in {"尺码选择", "尺码表", "尺码选择指南"}
    assert cluster.chunk_ids == ["c1"]
    assert cluster.claim_ids == ["cl1"]
    assert cluster.source_ids == ["s1"]
    assert cluster.knowledge_base_id == "kb1"
    assert cluster.status == "active"
    assert cluster.content_hash


def test_build_filters_empty_buckets():
    orphan_claim = _claim(claim_id="cl2", subject="孤立主题")
    clusters = build_topic_clusters(
        knowledge_base_id="kb1",
        chunks=[],
        claims=[orphan_claim],
        min_chunks=2,
    )
    assert len(clusters) == 1
    assert clusters[0].name == "孤立主题"
    assert clusters[0].claim_ids == ["cl2"]
    assert clusters[0].chunk_ids == []


def test_build_drops_buckets_without_chunks_or_claims():
    chunk = _chunk(topics=["冷门标签"], chunk_id="c2", source_id="s2")
    clusters = build_topic_clusters(
        knowledge_base_id="kb1",
        chunks=[chunk],
        claims=[],
        min_chunks=2,
    )
    assert clusters == []


def test_build_content_hash_stable():
    chunk = _chunk(topics=["尺码表"])
    claim = _claim()
    first = build_topic_clusters(knowledge_base_id="kb1", chunks=[chunk], claims=[claim])
    second = build_topic_clusters(knowledge_base_id="kb1", chunks=[chunk], claims=[claim])
    assert first[0].content_hash == second[0].content_hash
