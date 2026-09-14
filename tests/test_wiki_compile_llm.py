from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from infra.settings import Settings
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Claim, Source, SourceChunk, TopicCluster
from wiki.paths import compile_wiki_root


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


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_kb(knowledge: InMemoryKnowledge) -> None:
    knowledge.save_source(
        Source(
            id="src-a",
            title="policy_a.md",
            type="md",
            uri="file://src-a",
            version="1",
            created_at=_now(),
            status="active",
        )
    )
    knowledge.save_chunks(
        "src-a",
        [
            SourceChunk(
                id="c-a",
                source_id="src-a",
                chunk_index=0,
                title="chunk-0",
                summary="退款说明摘要",
                text="A 文档退款说明",
                start=0,
                end=10,
                topics=["退款政策"],
                status="active",
                created_at=_now(),
            )
        ],
    )
    knowledge.append_claim(
        Claim(
            id="claim-a",
            family_id="fam-a",
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
            source_ids=["src-a"],
        )
    )
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


def test_topic_merge_prompt_has_structured_sections():
    from wiki.prompts import build_topic_merge_prompt

    prompt = build_topic_merge_prompt(
        topic_name="退款政策",
        old_body="# 退款政策\n\n## 相关原文\n- [[source-src-a|policy_a.md]]\n",
        evidence={"chunks": [{"summary": "新摘要"}], "claims": [{"predicate": "时效", "object": "7天"}]},
        required_wikilinks=["[[source-src-a|policy_a.md]]"],
    )
    assert "## 角色" in prompt
    assert "## 目标" in prompt
    assert "## 规则" in prompt
    assert "## 输出" in prompt
    assert "## 上下文" in prompt
    assert "只合并" in prompt or "不编造" in prompt
    assert "相关实体" in prompt
    assert "wikilink" in prompt.lower() or "[[source-" in prompt


def test_compile_uses_llm_merge_and_preserves_wikilinks(tmp_path: Path):
    from wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_kb(knowledge)

    llm_body = "\n".join(
        [
            "---",
            "tags: [topic]",
            "type: topic",
            "kb_id: kb1",
            "---",
            "",
            "# 退款政策",
            "",
            "## 摘要",
            "> LLM 合并后的摘要",
            "",
            "## 要点",
            "- 退款时效 7 天",
            "",
            "## 相关原文",
            "- [[source-src-a|policy_a.md]]",
            "",
            "## 相关实体",
            "- [[退款|退款]]",
            "",
            "## 相关主题",
            "- （无相关主题）",
            "",
        ]
    )
    client = FakeLlmClient(json.dumps({"markdown": llm_body}, ensure_ascii=False))
    settings = Settings(wiki_compile=True, wiki_compile_llm=True, data_root=str(tmp_path))

    report = compile_topics_for_source(
        knowledge,
        "kb1",
        "src-a",
        str(tmp_path),
        settings,
        graph=None,
        llm_client=client,
    )
    assert report.pages_written >= 1
    assert len(client.calls) == 1

    body = (compile_wiki_root(tmp_path, "kb1") / "topic-退款政策.md").read_text(encoding="utf-8")
    assert "LLM 合并后的摘要" in body
    assert "[[source-src-a|policy_a.md]]" in body
    assert "## 相关原文" in body
    assert "## 相关实体" in body
    assert "## 相关主题" in body


def test_compile_falls_back_to_template_on_llm_parse_failure(tmp_path: Path):
    from wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_kb(knowledge)

    client = FakeLlmClient("not-json{{{")
    settings = Settings(wiki_compile=True, wiki_compile_llm=True, data_root=str(tmp_path))

    report = compile_topics_for_source(
        knowledge,
        "kb1",
        "src-a",
        str(tmp_path),
        settings,
        graph=None,
        llm_client=client,
    )
    assert report.pages_written >= 1
    assert len(client.calls) == 1

    body = (compile_wiki_root(tmp_path, "kb1") / "topic-退款政策.md").read_text(encoding="utf-8")
    assert "LLM 合并后的摘要" not in body
    assert "## Chunks" in body or "## 相关 Chunk" in body
    assert "## Claims" in body
    assert "## 相关实体" in body
    assert "[[退款|退款]]" in body
    assert "[[source-src-a|policy_a.md]]" in body


def test_compile_skips_llm_when_flag_false(tmp_path: Path):
    from wiki.compile import compile_topics_for_source

    knowledge = InMemoryKnowledge()
    _seed_kb(knowledge)

    client = FakeLlmClient(json.dumps({"markdown": "SHOULD_NOT_APPEAR"}, ensure_ascii=False))
    settings = Settings(wiki_compile=True, wiki_compile_llm=False, data_root=str(tmp_path))

    compile_topics_for_source(
        knowledge,
        "kb1",
        "src-a",
        str(tmp_path),
        settings,
        graph=None,
        llm_client=client,
    )
    assert client.calls == []
    body = (compile_wiki_root(tmp_path, "kb1") / "topic-退款政策.md").read_text(encoding="utf-8")
    assert "SHOULD_NOT_APPEAR" not in body
    assert "[[source-src-a|policy_a.md]]" in body
