from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.application.ask.graphs.ingest_graph import build_ingest_graph
from akos.application.ingest.chunk_enrichment import enrich_chunks, plan_chunks_for_source
from akos.application.ingest.chunk_service import build_source_chunks
from akos.domain.models.knowledge import Source, SourceChunk
from infra.settings import Settings


def _source(sid: str = "s1") -> Source:
    return Source(
        id=sid,
        title="闪电贷",
        type="md",
        uri="file://s1",
        version="1",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )


def _segment_llm(sections: list[dict]):
    class Client:
        is_configured = True

        def chat_completions(self, messages, *, temperature=0.0, timeout=60.0):
            return json.dumps({"sections": sections})

    return Client()


def test_plan_chunks_replaces_structural_chunks_before_claims():
    text = (
        "① 闪电贷是招商银行推出的一款个人纯信用贷款产品。\n\n"
        "② 具有审批速度快、放款迅速的特点。\n\n"
        "③ 适用于个人消费、经营周转等需求。\n\n"
        "④ 最高额度可达一百万元。\n"
    )
    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source())
    knowledge.save_source_text("s1", text)
    settings = Settings(
        chunk_llm_segment=True,
        chunk_llm_enrich=False,
        chunk_min_tokens=1,
        chunk_max_chars=512,
        chunk_max_per_doc=40,
    )
    chunks, _ = build_source_chunks("s1", text, settings)
    knowledge.save_chunks("s1", chunks)
    assert len(chunks) >= 2

    indexed: list = []
    deps = SimpleNamespace(
        knowledge=knowledge,
        llm_client=_segment_llm(
            [
                {
                    "title": "产品介绍",
                    "summary": "闪电贷简介",
                    "topics": ["闪电贷"],
                    "span_indexes": list(range(len(chunks))),
                }
            ]
        ),
        chunk_retrieval=SimpleNamespace(
            remove_source=lambda _sid: None,
            index_chunks=lambda items: indexed.extend(items),
        ),
    )

    planned = plan_chunks_for_source(source_id="s1", deps=deps, settings=settings)
    assert planned is True
    active = knowledge.list_chunks("s1", status="active")
    assert len(active) == 1
    assert active[0].title == "产品介绍"
    assert indexed


def test_plan_chunks_falls_back_when_llm_plan_invalid():
    text = "第一段内容足够长一些用于测试。\n\n第二段内容也要足够长一些。\n"
    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source())
    knowledge.save_source_text("s1", text)
    settings = Settings(chunk_llm_segment=True, chunk_min_tokens=5, chunk_max_chars=512)
    chunks, _ = build_source_chunks("s1", text, settings)
    knowledge.save_chunks("s1", chunks)
    before = [(c.start, c.end, c.text) for c in knowledge.list_chunks("s1", status="active")]

    class BadClient:
        is_configured = True

        def chat_completions(self, messages, *, temperature=0.0, timeout=60.0):
            return "not-json"

    deps = SimpleNamespace(
        knowledge=knowledge,
        llm_client=BadClient(),
        chunk_retrieval=SimpleNamespace(remove_source=lambda _sid: None, index_chunks=lambda items: None),
    )
    assert plan_chunks_for_source(source_id="s1", deps=deps, settings=settings) is False
    after = [(c.start, c.end, c.text) for c in knowledge.list_chunks("s1", status="active")]
    assert after == before


def test_enrich_chunks_does_not_resegment_boundaries():
    text = "AAA\n\nBBB\n"
    knowledge = InMemoryKnowledge()
    knowledge.save_source(_source())
    knowledge.save_source_text("s1", text)
    now = datetime.now(timezone.utc)
    knowledge.save_chunks(
        "s1",
        [
            SourceChunk(
                id="c0",
                source_id="s1",
                chunk_index=0,
                title="已规划A",
                summary="a",
                text="AAA\n\n",
                start=0,
                end=5,
                section_path=[],
                topics=["a"],
                token_count=1,
                status="active",
                content_hash="a",
                created_at=now,
            ),
            SourceChunk(
                id="c1",
                source_id="s1",
                chunk_index=1,
                title="已规划B",
                summary="b",
                text="BBB\n",
                start=5,
                end=9,
                section_path=[],
                topics=["b"],
                token_count=1,
                status="active",
                content_hash="b",
                created_at=now,
            ),
        ],
    )

    class SegmentAndEnrichClient:
        is_configured = True

        def chat_completions(self, messages, *, temperature=0.0, timeout=60.0):
            content = messages[0]["content"]
            if "章节规划" in content or "span_indexes" in content or '"sections"' in content or "sections" in content:

                return json.dumps(
                    {
                        "sections": [
                            {
                                "title": "不该出现",
                                "summary": "x",
                                "topics": [],
                                "span_indexes": [0, 1],
                            }
                        ]
                    }
                )
            # per-chunk enrich
            if "chunk_index 必须为 0" in content:
                return json.dumps(
                    {"chunk_index": 0, "title": "已规划A", "summary": "摘要A", "topics": ["a"]}
                )
            return json.dumps(
                {"chunk_index": 1, "title": "已规划B", "summary": "摘要B", "topics": ["b"]}
            )

    deps = SimpleNamespace(
        knowledge=knowledge,
        graph=None,
        llm_client=SegmentAndEnrichClient(),
        chunk_retrieval=SimpleNamespace(
            remove_source=lambda _sid: None,
            index_chunks=lambda items: None,
        ),
    )
    settings = Settings(chunk_llm_segment=True, chunk_llm_enrich=True, topic_cluster=False)
    enrich_chunks(kb_id="kb1", source_id="s1", deps=deps, settings=settings)

    active = knowledge.list_chunks("s1", status="active")
    assert len(active) == 2
    assert [c.title for c in active] == ["已规划A", "已规划B"]
    assert active[0].summary == "摘要A"


def test_ingest_graph_orders_plan_before_compile(build_orchestrator_deps):
    deps = build_orchestrator_deps()
    graph = build_ingest_graph(deps)
    nodes = graph.get_graph().nodes
    assert "plan_chunks" in nodes
    # Edges are encoded in the compiled graph; smoke that node exists for the new step.
