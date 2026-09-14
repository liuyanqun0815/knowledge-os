from __future__ import annotations


def test_wiki_hierarchy_settings_defaults(monkeypatch):
    monkeypatch.delenv("AKOS_WIKI_HIERARCHY", raising=False)
    monkeypatch.delenv("AKOS_WIKI_HIERARCHY_LLM", raising=False)
    monkeypatch.delenv("AKOS_WIKI_MIGRATE_FLAT", raising=False)
    monkeypatch.delenv("AKOS_WIKI_MAX_RELATED", raising=False)
    from infra.settings import Settings

    s = Settings(_env_file=None)
    assert s.wiki_hierarchy is True
    assert s.wiki_hierarchy_llm is False
    assert s.wiki_migrate_flat is True
    assert s.wiki_max_related == 12
