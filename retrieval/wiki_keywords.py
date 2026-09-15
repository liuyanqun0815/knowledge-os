from __future__ import annotations

import re

_STOPWORDS = frozenset(
    {
        "的", "了", "吗", "呢", "啊", "吧", "么", "呀", "哦", "嗯",
        "是", "在", "有", "和", "与", "及", "或", "被", "把", "让",
        "就", "都", "也", "还", "很", "太", "更", "最", "会", "能",
        "可以", "怎么", "什么", "哪个", "哪些", "如何", "请问", "一下",
        "这个", "那个", "一个", "我们", "你们", "他们", "自己",
        "a", "an", "the", "is", "are", "to", "of", "for", "in", "on",
    }
)
_TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def extract_keywords(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    tokens: list[str] = []
    try:
        import jieba

        tokens = [t.strip() for t in jieba.lcut(raw) if t and t.strip()]
    except Exception:
        tokens = _TOKEN_RE.findall(raw)
    seen: set[str] = set()
    out: list[str] = []
    for token in tokens:
        if len(token) == 1 and not ("\u4e00" <= token <= "\u9fff"):
            continue
        if token.lower() in _STOPWORDS or token in _STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out
