"""Ecommerce CS wiki hierarchy seed maps (parents / snippets)."""

from __future__ import annotations

# raw → (hub, leaf_or_target, role)
_SNIPPETS: dict[str, tuple[str, str, str]] = {
    "不知道": ("客服话术", "禁用表达", "snippet"),
    "不归我管": ("客服话术", "禁用表达", "snippet"),
    "你找别人": ("客服话术", "禁用表达", "snippet"),
    "没办法": ("客服话术", "禁用表达", "snippet"),
    "不可能": ("客服话术", "禁用表达", "snippet"),
}

_PARENTS: dict[str, tuple[str, str | None, str]] = {
    "客服开场": ("客服话术", "开场", "leaf"),
    "开场": ("客服话术", "开场", "leaf"),
    "客服沟通": ("客服话术", "沟通规范", "leaf"),
    "客服话术规范": ("客服话术", "沟通规范", "leaf"),
    "客服话术": ("客服话术", None, "hub"),
    "投诉升级": ("投诉升级", None, "hub"),
}


def get_ecommerce_wiki_seeds() -> dict[str, dict[str, tuple[str, str | None, str]]]:
    """Return seed maps: ``parents`` / ``snippets`` → raw → (hub, leaf, role)."""
    return {
        "parents": dict(_PARENTS),
        "snippets": dict(_SNIPPETS),
    }
