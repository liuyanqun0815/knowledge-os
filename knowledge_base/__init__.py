from knowledge_base.models import KnowledgeBase
from akos.adapters.persistence.kb_pg import PgKnowledgeBaseRepo

__all__ = ["KnowledgeBase", "KnowledgeBasePort", "PgKnowledgeBaseRepo"]


def __getattr__(name: str):
    # Lazy: avoid cycle hub.knowledge_base → models → package __init__ → ports → hub
    if name == "KnowledgeBasePort":
        from akos.domain.ports.knowledge_base import KnowledgeBasePort

        return KnowledgeBasePort
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
