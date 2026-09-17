from knowledge_base.models import KnowledgeBase
from knowledge_base.pg_repo import PgKnowledgeBaseRepo

__all__ = ["KnowledgeBase", "KnowledgeBasePort", "PgKnowledgeBaseRepo"]


def __getattr__(name: str):
    # Lazy: avoid cycle hub.knowledge_base → models → package __init__ → ports → hub
    if name == "KnowledgeBasePort":
        from knowledge_base.ports import KnowledgeBasePort

        return KnowledgeBasePort
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
