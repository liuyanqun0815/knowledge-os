from orchestrator.synthesis import sanitize_synthesis_payload, validate_synthesis_result


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
