from akos.application.ask.trace_utils import normalize_agent_trace, trace_step


def test_normalize_agent_trace_maps_legacy_retrieve_step():
    raw = [
        {
            "node": "retrieve",
            "hit_count": 5,
            "claim_hits": 3,
            "chunk_hits": 2,
            "retrieval_mode": "hybrid",
        }
    ]
    steps = normalize_agent_trace(raw)
    assert len(steps) == 1
    assert steps[0]["node"] == "retrieve"
    assert steps[0]["status"] == "ok"
    assert "命中 5 条" in steps[0]["summary"]
    assert steps[0]["detail"]["retrieval_mode"] == "hybrid"


def test_trace_step_builds_expandable_detail():
    step = trace_step("verify", summary="核验 verified", detail={"claim_ids": ["c1"]})
    assert step["status"] == "ok"
    assert step["detail"] == {"claim_ids": ["c1"]}


def test_serialize_hit_for_trace_includes_chunk_fields():
    from akos.application.ask.trace_utils import serialize_hit_for_trace

    class FakeHit:
        hit_type = "chunk"
        score = 0.8123
        snippet = "七天无理由退货"
        chunk_id = "chunk-1"
        source_id = "source-1"
        claim_id = None

    class FakeKnowledge:
        def get_chunk(self, chunk_id: str):
            assert chunk_id == "chunk-1"
            from types import SimpleNamespace

            return SimpleNamespace(chunk_index=0, title="退货说明")

    payload = serialize_hit_for_trace(FakeHit(), FakeKnowledge())
    assert payload["chunk_id"] == "chunk-1"
    assert payload["chunk_index"] == 0
    assert payload["title"] == "退货说明"


def test_normalize_agent_trace_preserves_full_pipeline():
    steps = normalize_agent_trace(
        [
            trace_step("route_mode", detail={"retrieval_mode": "hybrid"}),
            trace_step("retrieve", detail={"hit_count": 2, "claim_hits": 1, "chunk_hits": 1}),
            trace_step("verify", detail={"claim_ids": [], "chunk_ids": ["ch1"], "verification_status": "verified"}),
            trace_step("synthesize", detail={"citation_count": 3}),
            trace_step("answer", detail={"confidence": 0.92, "answer_chars": 120}),
        ]
    )
    assert [step["node"] for step in steps] == ["route_mode", "retrieve", "verify", "synthesize", "answer"]
