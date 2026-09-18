from __future__ import annotations

from pathlib import Path
from typing import Any

from akos.application.wiki.meta import load_pages_meta, save_pages_meta
from akos.application.wiki.paths import compile_wiki_root
from akos.application.wiki.source_plan import (
    _prune_empty_dirs,
    _purge_stale_pages_for_source,
    rebuild_wiki_index,
    relink_wiki_pages,
)


def purge_wiki_for_deleted_source(
    *,
    kb_id: str,
    source_id: str,
    knowledge: Any,
    data_root: str | Path,
    settings: Any,
    graph: Any = None,
    llm_client: Any = None,
    wiki_retrieval: Any = None,
) -> dict[str, int]:
    """Remove sole-source wiki pages for a deleted source; recompile multi-source pages.

    Returns counts useful for tests/logging: ``deleted_pages``, ``recompiled_sources``.
    """
    if not getattr(settings, "wiki_compile", True):
        return {"deleted_pages": 0, "recompiled_sources": 0}

    wiki_root = compile_wiki_root(data_root, kb_id)
    if not wiki_root.is_dir():
        return {"deleted_pages": 0, "recompiled_sources": 0}

    pages_meta = load_pages_meta(wiki_root)
    if not pages_meta:
        return {"deleted_pages": 0, "recompiled_sources": 0}

    before_ids = set(pages_meta)
    # Drop every sole-source page belonging to the deleted source.
    _purge_stale_pages_for_source(wiki_root, pages_meta, source_id, keep_page_ids=set())

    sibling_sources: set[str] = set()
    empty_page_ids: list[str] = []
    for page_id, meta in list(pages_meta.items()):
        if source_id not in meta.source_ids:
            continue
        remaining = [sid for sid in meta.source_ids if sid != source_id]
        if not remaining:
            empty_page_ids.append(page_id)
            continue
        meta.source_ids = remaining
        for sid in remaining:
            if knowledge.get_source(sid) is not None:
                sibling_sources.add(sid)

    for page_id in empty_page_ids:
        meta = pages_meta.pop(page_id, None)
        if meta is None:
            continue
        target = wiki_root / meta.path
        if target.is_file():
            target.unlink()

    _prune_empty_dirs(wiki_root)
    save_pages_meta(wiki_root, pages_meta)
    rebuild_wiki_index(wiki_root, kb_id, pages_meta)
    relink_wiki_pages(wiki_root, settings, kb_id=kb_id)

    recompiled = 0
    if sibling_sources:
        from akos.application.wiki.compile import compile_topics_for_source

        compile_settings = settings
        if hasattr(settings, "model_copy"):
            compile_settings = settings.model_copy(update={"wiki_compile_llm": False})
        for sid in sorted(sibling_sources):
            compile_topics_for_source(
                knowledge,
                kb_id,
                sid,
                data_root,
                compile_settings,
                graph=graph,
                llm_client=llm_client,
            )
            recompiled += 1

    if wiki_retrieval is not None:
        index_wiki_root = getattr(wiki_retrieval, "index_wiki_root", None)
        if callable(index_wiki_root):
            index_wiki_root(wiki_root)

    deleted_pages = len(before_ids - set(pages_meta))
    return {"deleted_pages": deleted_pages, "recompiled_sources": recompiled}
