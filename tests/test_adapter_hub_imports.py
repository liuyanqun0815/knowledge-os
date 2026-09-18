def test_adapter_hub_identity_persistence_and_llm():
    from akos.adapters.files.local import LocalFileStore as FilesHub
    from akos.adapters.llm.client import OpenAiCompatibleClient as LlmHub
    from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge as KnowledgeHub
    from akos.adapters.persistence.pg_knowledge import PgKnowledge as PgHub
    from akos.adapters.retrieval.hybrid import HybridRetrieval as HybridHub
    from infra.files import LocalFileStore as FilesShim
    from infra.llm import OpenAiCompatibleClient as LlmShim
    from infra.pg_repos import PgKnowledge as PgShim
    from knowledge.memory_repo import InMemoryKnowledge as KnowledgeShim
    from retrieval.hybrid import HybridRetrieval as HybridShim

    assert KnowledgeHub is KnowledgeShim
    assert PgHub is PgShim
    assert LlmHub is LlmShim
    assert FilesHub is FilesShim
    assert HybridHub is HybridShim
