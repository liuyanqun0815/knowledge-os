from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# 短问 / 指代：缺主语时常见问法（需同时满足「问句不含领域实体」）
_INCOMPLETE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(那|这|它|该)(个|种|项|笔)?"),
    re.compile(r"(能退|可以退|能不能退|退货吗|支持吗|怎么退|如何退)"),
    re.compile(r"(多久|多少天|几时|什么时候).{0,6}$"),
    re.compile(r"(谁承担|运费谁|谁出运费|运费吗)"),
    re.compile(r"(时效|期限|有效期).{0,4}(呢|吗)?$"),
    re.compile(r"^(是不是|是否|有没有|能不能).{0,10}(吗|么|呢)?$"),
    re.compile(r"^.{1,12}(吗|呢|么)$"),
)


@dataclass(frozen=True)
class RewriteResult:
    text: str
    method: str  # alias | rule | llm | none
    anchor: str | None = None
    reason: str | None = None


def collect_domain_terms(ontology: Any, domain: Any) -> list[str]:
    """Longer terms first so '七天无理由退货' wins over '七天无理由'."""
    terms: set[str] = set()
    get_aliases = getattr(domain, "get_aliases", None)
    if callable(get_aliases):
        terms.update(str(item) for item in get_aliases() if item)
    for attr in ("_types", "_aliases"):
        mapping = getattr(ontology, attr, None)
        if isinstance(mapping, dict):
            terms.update(str(key) for key in mapping.keys() if key)
            if attr == "_aliases":
                terms.update(str(value) for value in mapping.values() if value)
    cleaned = {term.strip() for term in terms if isinstance(term, str) and term.strip()}
    return sorted(cleaned, key=len, reverse=True)


def question_has_domain_entity(question: str, terms: list[str]) -> bool:
    return any(term in question for term in terms)


def matches_incomplete_pattern(question: str) -> bool:
    text = question.strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _INCOMPLETE_PATTERNS)


def extract_anchor_from_episodes(episodes: list[dict[str, Any]], terms: list[str]) -> str | None:
    for episode in episodes:
        blob = " ".join(str(episode.get(key) or "") for key in ("q", "question", "a", "answer") if episode.get(key))
        for term in terms:
            if term and term in blob:
                return term
    return None


def try_rule_rewrite(
    question: str,
    *,
    episodes: list[dict[str, Any]],
    terms: list[str],
) -> RewriteResult | None:
    if not episodes or not terms:
        return None
    if question_has_domain_entity(question, terms):
        return None
    if not matches_incomplete_pattern(question):
        return None
    anchor = extract_anchor_from_episodes(episodes, terms)
    if not anchor:
        return None
    text = question.strip()
    if text.startswith(anchor):
        return None
    rewritten = f"{anchor}{text}"
    return RewriteResult(text=rewritten, method="rule", anchor=anchor, reason="incomplete_without_entity")


def build_rewrite_prompt(question: str, episodes: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for index, episode in enumerate(episodes[:3], start=1):
        q = str(episode.get("q") or episode.get("question") or "").strip()
        a = str(episode.get("a") or episode.get("answer") or "").strip()
        lines.append(f"{index}. Q: {q}")
        if a:
            lines.append(f"   A: {a[:255]}")
    history = "\n".join(lines) if lines else "（无）"
    return (
        "# 角色\n"
        "你是检索问句改写器。\n"
        "\n"
        "# 目标\n"
        "根据会话历史，把当前不完整的用户问题改写成完整、可检索的中文问句。\n"
        "\n"
        "# 规则\n"
        "- 只输出改写后的问句本身\n"
        "- 不要解释、不要回答问题、不要添加引号\n"
        "- 保留用户原意，补全省略的主语/对象\n"
        "\n"
        "# 输出\n"
        "一行完整问句，无其它内容。\n"
        "\n"
        "# 参考\n"
        f"## 历史会话\n{history}\n\n"
        f"## 当前问题\n{question}\n"
    )


def try_llm_rewrite(
    question: str,
    *,
    episodes: list[dict[str, Any]],
    llm_client: Any,
) -> RewriteResult | None:
    if not episodes or llm_client is None:
        return None
    if not getattr(llm_client, "is_configured", False):
        return None
    prompt = build_rewrite_prompt(question, episodes)
    raw = llm_client.chat_completions([{"role": "user", "content": prompt}], temperature=0.0)
    text = str(raw or "").strip().splitlines()[0].strip().strip("「」\"'")
    if not text or text == question.strip():
        return None
    return RewriteResult(text=text, method="llm", reason="llm_rewrite")
