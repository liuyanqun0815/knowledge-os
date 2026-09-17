from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

# Upload / job override; None → use Settings.subject_bind_mode.
_subject_bind_mode_override: ContextVar[str | None] = ContextVar("akos_subject_bind_mode", default=None)

# Prompt examples only — not an exhaustive lexicon. Post-process covers the same few patterns.
GENERIC_SUBJECT_EXAMPLES = (
    "本产品",
    "本理财产品",
    "本理财计划",
    "本计划",
    "该产品",
    "投资者",
    "客户",
    "托管人",
    "管理人",
)

_PRODUCT_DEIXIS = frozenset(
    {
        "本产品",
        "本理财产品",
        "本理财计划",
        "本计划",
        "该产品",
        "该理财产品",
        "该理财计划",
    }
)

_ROLE_DEIXIS = frozenset(
    {
        "投资者",
        "客户",
        "托管人",
        "管理人",
        "份额持有人",
    }
)

_PREFIXES = (
    "本理财产品",
    "本理财计划",
    "本产品",
    "本计划",
    "该理财产品",
    "该理财计划",
    "该产品",
)


def normalize_bind_mode(value: str | None, *, default: str = "auto") -> str:
    mode = (value or default).strip().lower()
    if mode in {"auto", "on", "off"}:
        return mode
    return default


@contextmanager
def subject_bind_mode_override(mode: str | None) -> Iterator[None]:
    token = _subject_bind_mode_override.set(mode)
    try:
        yield
    finally:
        _subject_bind_mode_override.reset(token)


def effective_subject_bind_mode(settings_mode: str = "auto") -> str:
    override = _subject_bind_mode_override.get()
    if override is not None:
        return normalize_bind_mode(override, default=settings_mode)
    return normalize_bind_mode(settings_mode)


def bind_enabled(mode: str) -> bool:
    return normalize_bind_mode(mode) in {"auto", "on"}


def bind_generic_subject(subject: str, document_anchor: str | None) -> str:
    """Deterministic safety net when LLM leaves a deictic subject unbound."""
    text = (subject or "").strip()
    anchor = (document_anchor or "").strip()
    if not text or not anchor:
        return text
    if text == anchor or text.startswith(f"{anchor}的"):
        return text
    if text in _PRODUCT_DEIXIS:
        return anchor
    if text in _ROLE_DEIXIS:
        return f"{anchor}的{text}"
    for prefix in _PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix):
            rest = text[len(prefix) :].lstrip("的 \t")
            if rest:
                return f"{anchor}的{rest}"
            return anchor
    # Soft catch: short 「本…产品/计划」 without a concrete company name.
    if (
        text.startswith("本")
        and any(token in text for token in ("产品", "计划", "理财"))
        and "公司" not in text
        and len(text) <= 16
    ):
        return anchor
    return text


def subject_bind_prompt_rules(document_anchor: str) -> list[str]:
    examples = "、".join(GENERIC_SUBJECT_EXAMPLES)
    return [
        f"document_anchor={document_anchor}",
        "若 subject 是相对本文的泛化/指代说法（示例："
        + examples
        + "，以及类似的「本…产品/计划」+角色），必须用 document_anchor 改写："
        "本产品/本理财计划/本理财产品→document_anchor；"
        "投资者/客户→{document_anchor}的投资者；"
        "本理财产品托管人→{document_anchor}的托管人。"
        "以上仅为示例，非穷举；对同类指代主体套用同一模式。",
        "本段已出现与 document_anchor 不同的具体产品名/公司名时，优先用该具体名，不要强行替换。",
        "禁止单独用属性词作 subject（利率、额度、还款方式等）。",
    ]
