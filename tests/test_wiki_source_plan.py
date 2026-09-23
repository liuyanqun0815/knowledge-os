"""Source-centric wiki compilation with LLM planning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.models.knowledge import Claim, Source, SourceChunk
from akos.application.wiki.paths import compile_wiki_root
from akos.application.wiki.source_plan import (
    _evidence_for_page,
    _source_text_for_page,
    infer_source_layout,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeLlmClient:
    is_configured = True

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict] = []

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        timeout: float = 60.0,
    ) -> str:
        self.calls.append({"messages": messages, "temperature": temperature, "timeout": timeout})
        return self.response


def _size_guide_plan_client() -> FakeLlmClient:
    llm_body = "\n".join(
        [
            "# 尺码选择指南",
            "",
            "## 摘要",
            "> 服装与鞋码对照及选码建议",
            "",
            "## 问答",
            "### 尺码不合适能退吗？",
            "- **答**：支持七天无理由退换（需商品完好）",
            "- **来源**：[[source-商品咨询__尺码选择指南|尺码选择指南.md]]",
            "",
            "## 相关原文",
            "- [[source-商品咨询__尺码选择指南|尺码选择指南.md]]",
            "",
            "## Chunks",
            "- [[chunk-商品咨询__尺码选择指南-0|尺码选择指南]]: 对照表",
            "",
            "## 相关实体",
            "- [[退换货政策|退换货政策]]",
            "",
        ]
    )
    return FakeLlmClient(
        json.dumps(
            {
                "pages": [
                    {
                        "folder": "商品咨询",
                        "slug": "尺码选择指南",
                        "title": "尺码选择指南",
                        "markdown": llm_body,
                    }
                ]
            },
            ensure_ascii=False,
        )
    )


def _after_sales_plan_client() -> FakeLlmClient:
    markdown = "\n".join(
        [
            "# 七天无理由退货",
            "",
            "## 摘要",
            "> 尺码不合适可退货",
            "",
            "## 相关原文",
            "- [[source-售后__七天无理由退货|七天无理由退货.md]]",
            "",
            "## Chunks",
            "- [[chunk-售后__七天无理由退货-0|七天无理由退货]]: 说明",
            "",
        ]
    )
    return FakeLlmClient(
        json.dumps(
            {
                "pages": [
                    {
                        "folder": "售后",
                        "slug": "七天无理由退货",
                        "title": "七天无理由退货",
                        "markdown": markdown,
                    }
                ]
            },
            ensure_ascii=False,
        )
    )


def _seed_size_guide_kb(knowledge: InMemoryKnowledge) -> None:
    source_id = "商品咨询__尺码选择指南"
    knowledge.save_source_text(
        source_id,
        "\n".join(
            [
                "# 尺码选择指南",
                "",
                "## 服装尺码对照",
                "### 女装尺码（常见）",
                "| 尺码 | 胸围 |",
                "| S | 82-86 |",
                "",
                "## 退换货提醒",
                "- 尺码不合适：支持七天无理由退换",
            ]
        ),
    )
    knowledge.save_source(
        Source(
            id=source_id,
            title="尺码选择指南.md",
            type="md",
            uri=f"file://{source_id}",
            version="1",
            created_at=_now(),
            status="active",
        )
    )
    knowledge.save_chunks(
        source_id,
        [
            SourceChunk(
                id="c-size",
                source_id=source_id,
                chunk_index=0,
                title="尺码选择指南",
                summary="服装与鞋码对照表及选码建议",
                text="提供服装与鞋码的对照表及选码建议",
                start=0,
                end=20,
                section_path=["服装尺码对照"],
                topics=["尺码选择"],
                status="active",
                created_at=_now(),
            )
        ],
    )
    knowledge.append_claim(
        Claim(
            id="cl-return",
            family_id="fam-return",
            version=1,
            subject="退换货政策",
            predicate="尺码不合适",
            object="支持七天无理由退换（需商品完好）",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=_now(),
            valid_to=None,
            source_ids=[source_id],
        )
    )
    knowledge.append_claim(
        Claim(
            id="cl-size-l",
            family_id="fam-size-l",
            version=1,
            subject="女装尺码L",
            predicate="对应三围",
            object="胸围90-94cm",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=_now(),
            valid_to=None,
            source_ids=[source_id],
        )
    )


def test_infer_source_layout_from_double_underscore() -> None:
    folder, slug = infer_source_layout("商品咨询__尺码选择指南", "尺码选择指南.md")
    assert folder == "商品咨询"
    assert slug == "尺码选择指南"


def test_compile_source_plan_writes_single_aggregated_page(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_size_guide_kb(knowledge)
    source_id = "商品咨询__尺码选择指南"

    client = _size_guide_plan_client()
    settings = Settings(
        wiki_compile=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    report = compile_topics_for_source(
        knowledge,
        "kb1",
        source_id,
        str(tmp_path),
        settings,
        graph=None,
        llm_client=client,
    )
    assert report.pages_written == 1
    assert len(client.calls) == 1

    wiki_root = compile_wiki_root(tmp_path, "kb1")
    page = wiki_root / "商品咨询" / "尺码选择指南.md"
    assert page.is_file()
    body = page.read_text(encoding="utf-8")
    assert "尺码不合适" in body
    assert "[[source-商品咨询__尺码选择指南|尺码选择指南.md]]" in body
    assert not (wiki_root / "女装尺码L").exists()
    assert not (wiki_root / "尺码不合适").exists()

    index_body = (wiki_root / "index.md").read_text(encoding="utf-8")
    assert "商品咨询" in index_body
    assert "尺码选择指南" in index_body


def test_compile_source_plan_raises_on_invalid_llm_json(tmp_path: Path) -> None:
    from akos.adapters.llm.client import LlmCallError
    from akos.application.wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_size_guide_kb(knowledge)
    source_id = "商品咨询__尺码选择指南"

    client = FakeLlmClient("not-json")
    settings = Settings(
        wiki_compile=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    with pytest.raises(LlmCallError, match="有效页面"):
        compile_topics_for_source(
            knowledge,
            "kb1",
            source_id,
            str(tmp_path),
            settings,
            graph=None,
            llm_client=client,
        )


def test_compile_bundle_fallback_clusters_by_chunk_topics(tmp_path: Path) -> None:
    from akos.application.wiki.source_plan import _render_bundle_fallback_plans

    knowledge = InMemoryKnowledge()
    source_id = "贷款产品合集"
    body = ("贷款产品说明。" * 600) + "\n".join(
        [
            "## 1. 个人信用贷款",
            "信用贷正文" * 200,
            "## 2. 房屋抵押贷款",
            "房贷正文" * 200,
        ]
    )
    knowledge.save_source_text(source_id, body)
    knowledge.save_source(
        Source(
            id=source_id,
            title="贷款产品合集.md",
            type="md",
            uri=f"file://{source_id}",
            version="1",
            created_at=_now(),
            status="active",
        )
    )
    knowledge.save_chunks(
        source_id,
        [
            SourceChunk(
                id="c-credit",
                source_id=source_id,
                chunk_index=0,
                title="个人信用贷款",
                summary="信用贷摘要",
                text="个人信用贷款无需抵押。",
                start=0,
                end=20,
                section_path=["个人信用贷款"],
                topics=["个人信用贷款"],
                status="active",
                created_at=_now(),
            ),
            SourceChunk(
                id="c-mortgage",
                source_id=source_id,
                chunk_index=1,
                title="房屋抵押贷款",
                summary="房贷摘要",
                text="房屋抵押贷款额度高。",
                start=20,
                end=40,
                section_path=["房屋抵押贷款"],
                topics=["房屋抵押贷款"],
                status="active",
                created_at=_now(),
            ),
            SourceChunk(
                id="c-auto",
                source_id=source_id,
                chunk_index=2,
                title="汽车贷款",
                summary="车贷摘要",
                text="汽车贷款专用于购车。",
                start=40,
                end=60,
                section_path=["汽车贷款"],
                topics=["汽车贷款"],
                status="active",
                created_at=_now(),
            ),
        ],
    )
    knowledge.append_claim(
        Claim(
            id="cl-credit-limit",
            family_id="fam-credit-limit",
            version=1,
            subject="个人信用贷款",
            predicate="额度范围",
            object="1万元-50万元",
            subject_type="Product",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=_now(),
            valid_to=None,
            source_ids=[source_id],
        )
    )

    chunks = knowledge.list_chunks(source_id, status="active")
    claims = knowledge.get_claims_for_source(source_id)
    plans = _render_bundle_fallback_plans(
        kb_id="kb1",
        folder="贷款产品/贷款产品合集",
        product_name="贷款产品合集",
        source_id=source_id,
        source_title="贷款产品合集.md",
        source_text=body,
        chunks=chunks,
        claims=claims,
        related_links=[],
    )
    assert len(plans) >= 4
    credit_plan = next(p for p in plans if p.slug == "个人信用贷款")
    assert "## 要点" in credit_plan.markdown
    assert "### 个人信用贷款：额度范围" in credit_plan.markdown


def test_compile_bundle_fallback_uses_topics_not_rigid_chapters(tmp_path: Path) -> None:
    from akos.application.wiki.source_plan import _render_bundle_fallback_plans

    knowledge = InMemoryKnowledge()
    source_id = "青银理财成就系列"
    body = "青银理财产品说明书前言，业绩比较基准与托管人说明。\n" + ("条款内容" * 1500)
    assert len(body) >= 5000
    knowledge.save_source_text(source_id, body)
    knowledge.save_source(
        Source(
            id=source_id,
            title="青银理财成就系列（低波共享）.md",
            type="md",
            uri=f"file://{source_id}",
            version="1",
            created_at=_now(),
            status="active",
        )
    )
    knowledge.save_chunks(
        source_id,
        [
            SourceChunk(
                id="c-risk",
                source_id=source_id,
                chunk_index=0,
                title="风险揭示",
                summary="风险摘要",
                text="风险内容",
                start=0,
                end=10,
                topics=["风险揭示"],
                status="active",
                created_at=_now(),
            ),
            SourceChunk(
                id="c-fee",
                source_id=source_id,
                chunk_index=1,
                title="产品费用",
                summary="费用摘要",
                text="费用内容",
                start=10,
                end=20,
                topics=["产品费用"],
                status="active",
                created_at=_now(),
            ),
            SourceChunk(
                id="c-redeem",
                source_id=source_id,
                chunk_index=2,
                title="申购赎回",
                summary="赎回摘要",
                text="赎回内容",
                start=20,
                end=30,
                topics=["申购赎回"],
                status="active",
                created_at=_now(),
            ),
        ],
    )
    chunks = knowledge.list_chunks(source_id, status="active")
    plans = _render_bundle_fallback_plans(
        kb_id="kb1",
        folder="理财产品/青银理财成就系列（低波共享）",
        product_name="青银理财成就系列（低波共享）",
        source_id=source_id,
        source_title="青银理财成就系列（低波共享）.md",
        source_text=body,
        chunks=chunks,
        claims=[],
        related_links=[],
    )
    assert len(plans) >= 4
    fee_plan = next(p for p in plans if p.slug == "产品费用")
    assert "## 要点" in fee_plan.markdown
    assert "## 常见问题" in fee_plan.markdown
    assert "## 问答" not in fee_plan.markdown


def test_compile_source_plan_purges_old_fragmented_pages(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_size_guide_kb(knowledge)
    source_id = "商品咨询__尺码选择指南"
    wiki_root = compile_wiki_root(tmp_path, "kb1")
    stale_dir = wiki_root / "女装尺码L"
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "_index.md").write_text("# stale\n", encoding="utf-8")
    (wiki_root / ".meta").mkdir(parents=True, exist_ok=True)
    (wiki_root / ".meta" / "pages.json").write_text(
        json.dumps(
            {
                "女装尺码L/_index": {
                    "path": "女装尺码L/_index.md",
                    "title": "女装尺码L",
                    "kind": "hub",
                    "content_hash": "x",
                    "source_ids": [source_id],
                    "updated_at": None,
                }
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    settings = Settings(
        wiki_compile=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    compile_topics_for_source(
        knowledge,
        "kb1",
        source_id,
        str(tmp_path),
        settings,
        graph=None,
        llm_client=_size_guide_plan_client(),
    )
    assert not stale_dir.exists()
    assert (wiki_root / "商品咨询" / "尺码选择指南.md").is_file()


def test_compile_source_plan_injects_related_topics(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_size_guide_kb(knowledge)

    knowledge.save_source_text(
        "售后__七天无理由退货",
        "# 七天无理由退货\n\n尺码不合适可退货\n",
    )
    knowledge.save_source(
        Source(
            id="售后__七天无理由退货",
            title="七天无理由退货.md",
            type="md",
            uri="file://售后__七天无理由退货",
            version="1",
            created_at=_now(),
            status="active",
        )
    )

    settings = Settings(
        wiki_compile=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    compile_topics_for_source(
        knowledge,
        "kb1",
        "商品咨询__尺码选择指南",
        str(tmp_path),
        settings,
        graph=None,
        llm_client=_size_guide_plan_client(),
    )
    compile_topics_for_source(
        knowledge,
        "kb1",
        "售后__七天无理由退货",
        str(tmp_path),
        settings,
        graph=None,
        llm_client=_after_sales_plan_client(),
    )

    size_body = (compile_wiki_root(tmp_path, "kb1") / "商品咨询" / "尺码选择指南.md").read_text(encoding="utf-8")
    assert "## 相关主题" in size_body
    assert "[[售后/七天无理由退货|七天无理由退货]]" in size_body


def test_compile_source_plan_relinks_existing_pages(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_size_guide_kb(knowledge)

    knowledge.save_source_text("售后__七天无理由退货", "# 七天无理由退货\n\n尺码不合适可退货\n")
    knowledge.save_source(
        Source(
            id="售后__七天无理由退货",
            title="七天无理由退货.md",
            type="md",
            uri="file://售后__七天无理由退货",
            version="1",
            created_at=_now(),
            status="active",
        )
    )

    settings = Settings(
        wiki_compile=True,
        data_root=str(tmp_path),
        _env_file=None,
    )
    wiki_root = compile_wiki_root(tmp_path, "kb1")
    (wiki_root / "商品咨询").mkdir(parents=True, exist_ok=True)
    (wiki_root / "商品咨询" / "尺码选择指南.md").write_text(
        "# 尺码选择指南\n\n## 摘要\n\n尺码不合适可七天无理由退货\n\n## Chunks\n- x\n",
        encoding="utf-8",
    )
    from akos.application.wiki.meta import save_pages_meta, WikiPageMeta

    save_pages_meta(
        wiki_root,
        {
            "商品咨询/尺码选择指南": WikiPageMeta(
                path="商品咨询/尺码选择指南.md",
                title="尺码选择指南",
                kind="source_page",
                content_hash="x",
                source_ids=["商品咨询__尺码选择指南"],
            )
        },
    )

    compile_topics_for_source(
        knowledge,
        "kb1",
        "售后__七天无理由退货",
        str(tmp_path),
        settings,
        graph=None,
        llm_client=_after_sales_plan_client(),
    )

    size_body = (wiki_root / "商品咨询" / "尺码选择指南.md").read_text(encoding="utf-8")
    assert "[[售后/七天无理由退货|七天无理由退货]]" in size_body


def test_topic_cluster_skips_size_code_entity_subjects() -> None:
    from akos.application.topics.cluster import build_topic_clusters

    now = datetime.now(timezone.utc)
    source_id = "商品咨询__尺码选择指南"
    chunks = [
        SourceChunk(
            id="c1",
            source_id=source_id,
            chunk_index=0,
            title="尺码选择指南",
            summary="选码",
            text="选码建议",
            start=0,
            end=4,
            topics=["尺码选择"],
            status="active",
            created_at=now,
        )
    ]
    claims = [
        Claim(
            id="cl1",
            family_id="f1",
            version=1,
            subject="女装尺码L",
            predicate="三围",
            object="90-94",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=now,
            valid_to=None,
            source_ids=[source_id],
        ),
        Claim(
            id="cl2",
            family_id="f2",
            version=1,
            subject="退换货政策",
            predicate="尺码不合适",
            object="七天无理由",
            subject_type="Concept",
            object_type="Concept",
            confidence=0.9,
            status="active",
            valid_from=now,
            valid_to=None,
            source_ids=[source_id],
        ),
    ]
    clusters = build_topic_clusters(
        knowledge_base_id="kb1",
        chunks=chunks,
        claims=claims,
        min_chunks=1,
    )
    names = {cluster.name for cluster in clusters}
    assert "女装尺码L" not in names
    assert "尺码选择" in names or "退换货政策" in names


def test_evidence_for_page_uses_different_chunk_windows_when_unmatched():
    evidence = {
        "source_id": "s1",
        "source_title": "闪电贷",
        "chunks": [{"title": f"段{i}", "summary": f"内容{i}", "excerpt": f"ex{i}"} for i in range(8)],
        "claims": [{"subject": f"主体{i}", "predicate": "p", "object": "o"} for i in range(10)],
    }
    a = _evidence_for_page(evidence, title="未知A", focus="include: foo", page_index=0)
    b = _evidence_for_page(evidence, title="未知B", focus="include: bar", page_index=3)
    assert a["chunks"] != b["chunks"]
    assert a["claims"] != b["claims"]


def test_source_text_for_page_prefers_chunk_excerpts():
    full = "全文" * 5000
    page_evidence = {
        "chunks": [{"title": "利率", "excerpt": "年化利率 3.15% 起"}],
    }
    text = _source_text_for_page(page_evidence, full, slug="利率与费用")
    assert "3.15%" in text
    assert len(text) < len(full)


def test_source_text_for_index_is_short():
    full = "x" * 5000
    text = _source_text_for_page({"chunks": []}, full, slug="_index")
    assert len(text) <= 1200
