from datetime import datetime, timezone
from pathlib import Path

import pytest

from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim, Source, SourceChunk, TopicCluster
from akos.application.wiki.export import _sanitize_filename, export_wiki, resolve_wiki_output_dir


def _source(source_id: str = "policy-v3", title: str = "refund_policy_v3.md") -> Source:
    return Source(
        id=source_id,
        title=title,
        type="policy",
        uri=f"file://{source_id}",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _claim(
    claim_id: str,
    family_id: str,
    *,
    subject: str = "七天无理由",
    predicate: str = "运费承担方",
    object_value: str = "买家",
    source_ids: list[str] | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        family_id=family_id,
        version=1,
        subject=subject,
        predicate=predicate,
        object=object_value,
        subject_type="RefundRule",
        object_type="Concept",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=source_ids or ["policy-v3"],
    )


def test_sanitize_filename_replaces_unsafe_chars():
    assert _sanitize_filename("a/b:c") == "a_b_c"


def test_export_wiki_writes_index_log_source_and_entity_pages(tmp_path: Path):
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("policy-v3", "七天无理由退货运费由买家承担。")
    knowledge.append_claim(_claim("claim-1", "family-1"))
    knowledge.append_claim(
        _claim(
            "claim-2",
            "family-2",
            predicate="排除",
            object_value="定制商品",
        )
    )

    output_dir = tmp_path / "wiki-out"
    result = export_wiki(knowledge, evidence, "legacy", output_dir)

    assert result.kb_id == "legacy"
    assert result.output_dir == output_dir
    assert result.source_pages == 1
    assert result.entity_pages == 1
    assert result.files_written == 4
    assert (output_dir / "index.md").exists()
    assert (output_dir / "log.md").exists()
    assert (output_dir / "source-policy-v3.md").exists()
    assert (output_dir / "七天无理由.md").exists()

    entity_content = (output_dir / "七天无理由.md").read_text(encoding="utf-8")
    assert "type: entity" in entity_content
    assert "## Claims" in entity_content
    assert "运费承担方 → 买家" in entity_content
    assert "排除 → 定制商品" in entity_content
    assert "[[source-policy-v3|refund_policy_v3.md]]" in entity_content

    source_content = (output_dir / "source-policy-v3.md").read_text(encoding="utf-8")
    assert "type: source" in source_content
    assert "refund_policy_v3.md" in source_content
    assert "[[七天无理由|七天无理由]]" in source_content

    index_content = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "Wiki Index — legacy" in index_content
    assert "[[source-policy-v3|refund_policy_v3.md]]" in index_content
    assert "[[七天无理由|七天无理由]]" in index_content


def test_export_wiki_writes_topic_pages_and_index_section(tmp_path: Path):
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    knowledge.save_source_text("policy-v3", "尺码选择相关说明。")
    knowledge.save_chunks(
        "policy-v3",
        [
            SourceChunk(
                id="chunk-1",
                source_id="policy-v3",
                chunk_index=0,
                title="尺码表",
                summary=None,
                text="请核对尺码表。",
                start=0,
                end=8,
                topics=["尺码选择"],
                status="active",
                created_at=datetime.now(timezone.utc),
            )
        ],
    )
    claim = _claim("claim-1", "family-1", subject="尺码选择", predicate="建议", object_value="核对尺码表")
    knowledge.append_claim(claim)
    knowledge.save_topic_clusters(
        [
            TopicCluster(
                id="topic-1",
                knowledge_base_id="legacy",
                name="尺码选择",
                aliases=["尺码表"],
                chunk_ids=["chunk-1"],
                claim_ids=["claim-1"],
                source_ids=["policy-v3"],
                summary="尺码相关主题",
                status="active",
                content_hash="hash-1",
                updated_at=datetime.now(timezone.utc),
            )
        ]
    )

    output_dir = tmp_path / "wiki-out"
    result = export_wiki(knowledge, evidence, "legacy", output_dir)

    assert result.topic_pages == 1
    topic_path = output_dir / "topic-尺码选择.md"
    assert topic_path.exists()
    topic_content = topic_path.read_text(encoding="utf-8")
    assert "type: topic" in topic_content
    assert "## Claims" in topic_content
    assert "建议 → 核对尺码表" in topic_content
    assert "[[source-policy-v3|refund_policy_v3.md]]" in topic_content
    assert "[[chunk-policy-v3-0|尺码表]]" in topic_content

    index_content = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "## 主题" in index_content
    topics_pos = index_content.index("## 主题")
    entities_pos = index_content.index("## Entities")
    assert topics_pos < entities_pos
    assert "[[topic-尺码选择|尺码选择]]" in index_content


def test_export_wiki_writes_topic_pages_to_hub_paths_when_hierarchy_on(tmp_path: Path):
    from infra.settings import Settings

    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source())
    claim = _claim("claim-1", "family-1", subject="客服沟通", predicate="要求", object_value="礼貌清晰")
    knowledge.append_claim(claim)
    knowledge.save_topic_clusters(
        [
            TopicCluster(
                id="topic-cs",
                knowledge_base_id="legacy",
                name="客服沟通",
                aliases=[],
                chunk_ids=[],
                claim_ids=["claim-1"],
                source_ids=["policy-v3"],
                summary="沟通规范要点",
                status="active",
                content_hash="hash-cs",
                updated_at=datetime.now(timezone.utc),
            )
        ]
    )

    output_dir = tmp_path / "wiki-out"
    result = export_wiki(
        knowledge,
        evidence,
        "legacy",
        output_dir,
        settings=Settings(wiki_hierarchy=True),
    )

    assert result.topic_pages == 1
    nested = output_dir / "客服话术" / "沟通规范.md"
    assert nested.exists()
    assert not (output_dir / "topic-客服沟通.md").exists()
    content = nested.read_text(encoding="utf-8")
    assert "# 客服沟通" in content or "# 沟通规范" in content
    assert "礼貌清晰" in content

    index_content = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "[[客服话术/沟通规范|" in index_content


def test_export_wiki_sanitizes_source_id_in_filename(tmp_path: Path):
    knowledge = InMemoryKnowledge()
    evidence = InMemoryEvidence()
    knowledge.save_source(_source("nested/path", "nested.md"))
    knowledge.append_claim(_claim("claim-1", "family-1", source_ids=["nested/path"]))

    output_dir = tmp_path / "wiki-out"
    export_wiki(knowledge, evidence, "legacy", output_dir)

    assert (output_dir / "source-nested_path.md").exists()


def test_resolve_wiki_output_dir_defaults_to_kb_wiki(tmp_path: Path):
    data_root = str(tmp_path / "data")
    output_dir = resolve_wiki_output_dir(data_root, "legacy")
    assert output_dir == (tmp_path / "data" / "legacy" / "wiki").resolve()


def test_resolve_wiki_output_dir_rejects_escape(tmp_path: Path):
    data_root = str(tmp_path / "data")

    with pytest.raises(ValueError, match="data root"):
        resolve_wiki_output_dir(data_root, "legacy", "../outside")
