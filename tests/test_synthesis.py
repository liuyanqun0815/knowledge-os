from orchestrator.synthesis import _build_prompt, sanitize_synthesis_payload, validate_synthesis_result


def test_build_prompt_separates_question_and_knowledge():
    context = {
        "question": "什么情况下退货不能免运费？",
        "claims": [{"id": "c1", "subject": "退货运费", "predicate": "承担方", "object": "买家", "confidence": 0.9}],
        "evidence": [],
        "chunks": [],
    }
    prompt = _build_prompt(context)
    assert "## 用户问题\n什么情况下退货不能免运费？" in prompt
    knowledge_section = prompt.split("## 参考知识\n", 1)[1]
    assert '"claims"' in knowledge_section
    assert '"question"' not in knowledge_section


def test_build_prompt_includes_wiki_section_and_grounding_rule():
    context = {
        "question": "退款政策概览？",
        "claims": [{"id": "c1", "subject": "退款", "predicate": "时效", "object": "7天", "confidence": 0.9}],
        "evidence": [],
        "chunks": [],
        "wiki_pages": [
            {
                "title": "退款政策",
                "excerpt": "主题页综述退款流程与例外",
                "path": "topic-退款政策.md",
                "links": ["[[source:policy]]"],
            }
        ],
    }
    prompt = _build_prompt(context)
    assert "## Wiki 主题页" in prompt
    assert "数字与规则以 Claim" in prompt or "数字与规则以 Claim/原文为准" in prompt
    assert "Wiki 仅作结构与综述" in prompt
    assert "退款政策" in prompt
    knowledge_section = prompt.split("## 参考知识\n", 1)[1]
    assert '"wiki_pages"' in knowledge_section


def test_sanitize_strips_inline_citations_from_answer():
    context = {
        "evidence": [{"source_id": "s1", "quote": "买家承担退货运费"}],
        "chunks": [],
    }
    sanitized = sanitize_synthesis_payload(
        context,
        {
            "answer": "退货运费由买家承担。[s1:买家承担退货运费]",
            "citations": [{"source_id": "s1", "quote": "买家承担退货运费", "claim_id": "c1", "chunk_id": None}],
        },
    )
    assert sanitized is not None
    assert sanitized["answer"] == "退货运费由买家承担。"
    assert len(sanitized["citations"]) == 1


def test_validate_synthesis_result_requires_grounded_citations():
    context = {
        "evidence": [{"source_id": "s1", "quote": "买家承担退货运费"}],
        "chunks": [],
    }
    valid = validate_synthesis_result(
        context,
        {
            "answer": "退货运费由买家承担。[s1:买家承担退货运费]",
            "citations": [{"source_id": "s1", "quote": "买家承担退货运费", "claim_id": "c1", "chunk_id": None}],
        },
    )
    assert valid is True

    invalid = validate_synthesis_result(
        context,
        {
            "answer": "编造的答案",
            "citations": [{"source_id": "s1", "quote": "不存在的内容", "claim_id": None, "chunk_id": None}],
        },
    )
    assert invalid is False


def test_sanitize_keeps_answer_when_citations_partially_invalid():
    context = {
        "evidence": [{"source_id": "规则_订单取消与退款", "quote": "已发货订单需要收到货后再申请退货退款"}],
        "chunks": [
            {
                "source_id": "规则_订单取消与退款",
                "text_excerpt": "已发货订单需要收到货后再申请退货退款。定制商品不支持取消。",
                "summary": None,
                "quote": "已发货订单需要收到货后再申请退货退款",
            }
        ],
    }
    payload = {
        "answer": "已发货订单需要收到货后再申请退货退款。",
        "citations": [
            {
                "source_id": "规则_订单取消与退款",
                "quote": "已发货订单需要收到货后再申请退货退款",
                "claim_id": None,
                "chunk_id": "chunk-1",
            },
            {
                "source_id": "规则_订单取消与退款",
                "quote": "LLM 编造的引用",
                "claim_id": None,
                "chunk_id": None,
            },
        ],
    }
    sanitized = sanitize_synthesis_payload(context, payload)
    assert sanitized is not None
    assert sanitized["answer"] == payload["answer"]
    assert len(sanitized["citations"]) == 1


def test_build_synthesis_context_uses_rerank_hits_and_truncates_non_claims():
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from infra.settings import Settings
    from knowledge.models import Claim, SourceChunk
    from orchestrator.synthesis import build_synthesis_context
    from retrieval.ports import Hit

    claim = Claim(
        id="cl1",
        family_id="f1",
        version=1,
        subject="发货",
        predicate="时效",
        object="48小时",
        subject_type="concept",
        object_type="literal",
        confidence=0.9,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_to=None,
        source_ids=["s1"],
    )
    long_text = "A" * 1200
    chunk = SourceChunk(
        id="ch1",
        source_id="s1",
        chunk_index=0,
        title="发货说明",
        summary="摘要",
        text=long_text,
        start=0,
        end=1200,
        status="active",
    )
    chunk2 = SourceChunk(
        id="ch2",
        source_id="s1",
        chunk_index=1,
        title="补充",
        summary=None,
        text="短正文",
        start=0,
        end=3,
        status="active",
    )
    chunks_by_id = {"ch1": chunk, "ch2": chunk2}
    knowledge = SimpleNamespace(
        get_claim=lambda cid: claim if cid == "cl1" else None,
        get_chunk=lambda cid: chunks_by_id.get(cid),
    )
    evidence = SimpleNamespace(explain=lambda ids: SimpleNamespace(items=[]))
    deps = SimpleNamespace(knowledge=knowledge, evidence=evidence)
    settings = Settings(_env_file=None, ask_synthesis_max_chunks=1, ask_synthesis_content_max_chars=800)

    hits = [
        Hit(score=1.0, snippet="claim", hit_type="claim", claim_id="cl1"),
        Hit(score=0.9, snippet="chunk", hit_type="chunk", chunk_id="ch1", source_id="s1"),
        Hit(
            score=0.8,
            snippet="wiki",
            hit_type="wiki",
            ref_id="物流/发货",
            path="物流/发货.md",
            title="发货时效",
            content="B" * 1000,
        ),
        Hit(score=0.7, snippet="chunk2", hit_type="chunk", chunk_id="ch2", source_id="s1"),
    ]

    context = build_synthesis_context(
        question="发货多久？",
        claim_ids=["cl1"],
        chunk_ids=["ch1"],
        wiki_pages=[{"title": "旧页", "content": "旧", "path": "old.md"}],
        hits=hits,
        deps=deps,
        settings=settings,
    )

    assert [c["id"] for c in context["claims"]] == ["cl1"]
    # hits 路径忽略 ask_synthesis_max_chunks，按 rerank 顺序消费全部非 Claim
    assert [c["id"] for c in context["chunks"]] == ["ch1", "ch2"]
    assert len(context["chunks"][0]["text_excerpt"]) == 800
    assert len(context["wiki_pages"]) == 1
    assert context["wiki_pages"][0]["path"] == "物流/发货.md"
    assert len(context["wiki_pages"][0]["content"]) == 800
