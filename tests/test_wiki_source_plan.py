"""Source-centric wiki compilation with LLM planning."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from infra.settings import Settings
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from knowledge.models import Claim, Source, SourceChunk
from akos.application.wiki.paths import compile_wiki_root
from akos.application.wiki.source_plan import infer_source_layout


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
    client = FakeLlmClient(
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
    settings = Settings(
        wiki_compile=True,
        wiki_hierarchy=True,
        wiki_source_plan=True,
        wiki_source_plan_llm=True,
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


def test_compile_source_plan_falls_back_to_template(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_size_guide_kb(knowledge)
    source_id = "商品咨询__尺码选择指南"

    client = FakeLlmClient("not-json")
    settings = Settings(
        wiki_compile=True,
        wiki_hierarchy=True,
        wiki_source_plan=True,
        wiki_source_plan_llm=True,
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
    page = compile_wiki_root(tmp_path, "kb1") / "商品咨询" / "尺码选择指南.md"
    body = page.read_text(encoding="utf-8")
    assert "## 要点" in body
    assert "## 常见问题" in body
    assert "七天无理由退换" in body
    assert "退换货政策" in body  # FAQ 需带 subject
    # 要点不应只剩一句空泛摘要：至少 2 条
    assert body.count("\n- ") >= 2


def test_compile_bundle_fallback_clusters_by_chunk_topics(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

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

    settings = Settings(
        wiki_compile=True,
        wiki_hierarchy=True,
        wiki_source_plan=True,
        wiki_source_plan_llm=False,
        wiki_split_min_chars=5000,
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
        llm_client=None,
    )
    wiki_root = compile_wiki_root(tmp_path, "kb1")
    assert (wiki_root / "贷款产品" / "贷款产品合集" / "_index.md").is_file()
    assert (wiki_root / "贷款产品" / "贷款产品合集" / "个人信用贷款.md").is_file()
    assert (wiki_root / "贷款产品" / "贷款产品合集" / "房屋抵押贷款.md").is_file()
    assert (wiki_root / "贷款产品" / "贷款产品合集" / "汽车贷款.md").is_file()
    assert report.pages_written >= 4

    credit = (wiki_root / "贷款产品" / "贷款产品合集" / "个人信用贷款.md").read_text(encoding="utf-8")
    assert "## 要点" in credit
    assert "## 常见问题" in credit
    assert "### 个人信用贷款：额度范围" in credit
    assert credit.count("### ") <= 8


def test_compile_bundle_fallback_uses_topics_not_rigid_chapters(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source

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
    settings = Settings(
        wiki_compile=True,
        wiki_hierarchy=True,
        wiki_source_plan=True,
        wiki_source_plan_llm=False,
        wiki_split_min_chars=5000,
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
        llm_client=None,
    )
    wiki_root = compile_wiki_root(tmp_path, "kb1")
    product_dir = wiki_root / "理财产品" / "青银理财成就系列（低波共享）"
    assert (product_dir / "_index.md").is_file()
    assert (product_dir / "风险揭示.md").is_file()
    assert (product_dir / "产品费用.md").is_file()
    assert (product_dir / "申购赎回.md").is_file()
    assert report.pages_written >= 4
    fee = (product_dir / "产品费用.md").read_text(encoding="utf-8")
    assert "## 要点" in fee
    assert "## 常见问题" in fee
    assert "## 问答" not in fee


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
        wiki_hierarchy=True,
        wiki_source_plan=True,
        wiki_source_plan_llm=True,
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
        llm_client=None,
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
        wiki_hierarchy=True,
        wiki_source_plan_llm=False,
        data_root=str(tmp_path),
        _env_file=None,
    )
    compile_topics_for_source(
        knowledge, "kb1", "商品咨询__尺码选择指南", str(tmp_path), settings, graph=None, llm_client=None
    )
    compile_topics_for_source(
        knowledge, "kb1", "售后__七天无理由退货", str(tmp_path), settings, graph=None, llm_client=None
    )

    size_body = (compile_wiki_root(tmp_path, "kb1") / "商品咨询" / "尺码选择指南.md").read_text(encoding="utf-8")
    assert "## 相关主题" in size_body
    assert "[[售后/七天无理由退货|七天无理由退货]]" in size_body


def test_compile_source_plan_relinks_existing_pages(tmp_path: Path) -> None:
    from akos.application.wiki.compile import compile_topics_for_source
    from akos.application.wiki.source_plan import relink_wiki_pages

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
        wiki_hierarchy=True,
        wiki_source_plan=True,
        wiki_source_plan_llm=False,
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
        knowledge, "kb1", "售后__七天无理由退货", str(tmp_path), settings, graph=None, llm_client=None
    )

    size_body = (wiki_root / "商品咨询" / "尺码选择指南.md").read_text(encoding="utf-8")
    assert "[[售后/七天无理由退货|七天无理由退货]]" in size_body


def test_topic_cluster_skips_size_code_entity_subjects() -> None:
    from knowledge.topic_cluster import build_topic_clusters

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
