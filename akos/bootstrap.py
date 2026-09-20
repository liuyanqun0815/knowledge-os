from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from akos.application.ingest.service import KnowledgeCompiler
from akos.domain.ports.domain import DomainPort
from akos.domains.registry import load_domain
from akos.application.evolution.service import EvolutionService
from akos.adapters.persistence.evidence_memory import InMemoryEvidence
from akos.domain.ports.evidence import EvidencePort
from akos.adapters.persistence.graph_memory import InMemoryGraph
from akos.domain.ports.graph import GraphPort
from akos.adapters.files.local import LocalFileStore
from akos.adapters.llm.client import OpenAiCompatibleClient
from akos.adapters.persistence.pg_knowledge import PgKnowledge
from infra.settings import Settings
from akos.domain.errors import DomainError
from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
from akos.domain.ports.knowledge import KnowledgePort
from akos.domain.models.knowledge_base import KnowledgeBase
from akos.adapters.persistence.memory_store import InMemoryMemoryStore
from akos.domain.ports.memory import MemoryPort
from akos.adapters.ontology.memory import InMemoryOntology
from akos.application.ask.service import LangGraphOrchestrator
from akos.adapters.retrieval.hybrid import HybridRetrieval
from akos.adapters.retrieval.chunk_index import ChunkRetrieval
from akos.adapters.retrieval.embedder import create_embedder
from akos.adapters.retrieval.reranker import create_reranker
from akos.adapters.retrieval.wiki_index import WikiPageRetrieval
from akos.application.ask.verification import VerificationService
from akos.application.wiki.paths import compile_wiki_root

DEFAULT_IN_MEMORY_KB_ID = "default"
LEGACY_PG_KB_ID = "legacy"


@dataclass
class OrchestratorDeps:
    files: LocalFileStore
    knowledge: KnowledgePort
    ontology: InMemoryOntology
    graph: GraphPort
    evidence: EvidencePort
    compiler: KnowledgeCompiler
    llm_client: OpenAiCompatibleClient
    retrieval: HybridRetrieval
    chunk_retrieval: ChunkRetrieval
    memory: MemoryPort
    domain: DomainPort
    evolution: EvolutionService
    verification: VerificationService
    knowledge_base_id: str
    wiki_retrieval: WikiPageRetrieval | None = None
    reranker: object | None = None


@dataclass
class WikiCompileDeps:
    """Lightweight deps for wiki compile/export — no embedder / rerank / retrieval warm-up."""

    knowledge: KnowledgePort
    graph: GraphPort
    llm_client: OpenAiCompatibleClient
    wiki_retrieval: WikiPageRetrieval | None = None


def build_wiki_compile_deps(
    knowledge_base_id: str,
    settings: Settings | None = None,
    *,
    existing: OrchestratorDeps | None = None,
) -> WikiCompileDeps:
    """Build wiki-compile deps without loading embedding/rerank stacks.

    If ``existing`` orchestrator deps are already warmed (e.g. in-memory test cache),
    reuse their knowledge/graph so compile sees the same store. Otherwise build a
    fresh repo + LLM client only.
    """
    cfg = settings or Settings()
    if existing is not None:
        wiki_retrieval = existing.wiki_retrieval
        if wiki_retrieval is None and cfg.wiki_compile:
            wiki_retrieval = WikiPageRetrieval(llm_client=existing.llm_client)
        return WikiCompileDeps(
            knowledge=existing.knowledge,
            graph=existing.graph,
            llm_client=existing.llm_client,
            wiki_retrieval=wiki_retrieval,
        )

    _resolve_kb(knowledge_base_id, cfg)
    knowledge, graph, _, _ = _build_repos(knowledge_base_id, cfg)
    llm_client = OpenAiCompatibleClient(cfg)
    wiki_retrieval = WikiPageRetrieval(llm_client=llm_client) if cfg.wiki_compile else None
    return WikiCompileDeps(
        knowledge=knowledge,
        graph=graph,
        llm_client=llm_client,
        wiki_retrieval=wiki_retrieval,
    )


def build_pg_knowledge(knowledge_base_id: str = LEGACY_PG_KB_ID) -> PgKnowledge:
    from infra.db import get_engine

    settings = Settings()
    return PgKnowledge(get_engine(settings), knowledge_base_id)


def _get_kb_repo(settings: Settings):
    if not settings.use_pg:
        return None
    from infra.db import get_engine
    from akos.adapters.persistence.kb_pg import PgKnowledgeBaseRepo

    return PgKnowledgeBaseRepo(get_engine(settings))


def _resolve_kb(knowledge_base_id: str, settings: Settings) -> KnowledgeBase:
    if settings.use_pg:
        kb_repo = _get_kb_repo(settings)
        assert kb_repo is not None
        kb = kb_repo.get(knowledge_base_id)
        if kb is None or kb.status != "active":
            raise DomainError(f"knowledge_base_not_found: {knowledge_base_id}")
        return kb

    now = datetime.now(timezone.utc)
    return KnowledgeBase(
        id=knowledge_base_id,
        name=knowledge_base_id,
        domain_type=settings.default_domain_type,
        description="",
        status="active",
        created_at=now,
        updated_at=now,
    )


def _build_graph(settings: Settings, engine, kb_id: str) -> GraphPort:
    backend = settings.graph_backend.lower()
    if backend == "neo4j":
        from akos.adapters.graph.neo4j import Neo4jGraph

        return Neo4jGraph(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            knowledge_base_id=kb_id,
        )
    if backend == "postgres" and settings.use_pg and engine is not None:
        from akos.adapters.persistence.pg_graph import PgGraph

        return PgGraph(engine, kb_id)
    return InMemoryGraph()


def _build_repos(
    knowledge_base_id: str, settings: Settings
) -> tuple[KnowledgePort, GraphPort, EvidencePort, MemoryPort]:
    if settings.use_pg:
        from infra.db import get_engine
        from akos.adapters.persistence.pg_evidence import PgEvidence
        from akos.adapters.persistence.pg_memory import PgMemory

        engine = get_engine(settings)
        return (
            PgKnowledge(engine, knowledge_base_id),
            _build_graph(settings, engine, knowledge_base_id),
            PgEvidence(engine, knowledge_base_id),
            PgMemory(engine, knowledge_base_id),
        )
    return (
        InMemoryKnowledge(),
        _build_graph(settings, None, knowledge_base_id),
        InMemoryEvidence(),
        InMemoryMemoryStore(),
    )



_SHARED_EMBEDDER = None
_SHARED_EMBEDDER_KEY: tuple | None = None
_SHARED_RERANKER = None
_SHARED_RERANKER_KEY: tuple | None = None


def reset_shared_model_cache() -> None:
    global _SHARED_EMBEDDER, _SHARED_EMBEDDER_KEY, _SHARED_RERANKER, _SHARED_RERANKER_KEY
    _SHARED_EMBEDDER = None
    _SHARED_EMBEDDER_KEY = None
    _SHARED_RERANKER = None
    _SHARED_RERANKER_KEY = None


def _embedder_cache_key(settings: Settings) -> tuple:
    return (
        settings.embedding_enabled,
        settings.embedding_provider,
        settings.embedding_model,
        settings.embedding_model_source,
        settings.embedding_dims,
        settings.embedding_device,
        settings.embedding_cache_dir,
        settings.hf_endpoint,
    )


def _reranker_cache_key(settings: Settings) -> tuple:
    return (
        settings.rerank_enabled,
        settings.rerank_provider,
        settings.rerank_model,
        settings.rerank_model_source,
        settings.rerank_device,
        settings.rerank_cache_dir,
        settings.rerank_max_length,
    )


def _get_shared_embedder(settings: Settings):
    global _SHARED_EMBEDDER, _SHARED_EMBEDDER_KEY
    key = _embedder_cache_key(settings)
    if _SHARED_EMBEDDER is not None and _SHARED_EMBEDDER_KEY == key:
        return _SHARED_EMBEDDER
    _SHARED_EMBEDDER = create_embedder(settings)
    _SHARED_EMBEDDER_KEY = key
    return _SHARED_EMBEDDER


def _get_shared_reranker(settings: Settings):
    global _SHARED_RERANKER, _SHARED_RERANKER_KEY
    key = _reranker_cache_key(settings)
    if _SHARED_RERANKER is not None and _SHARED_RERANKER_KEY == key:
        return _SHARED_RERANKER
    _SHARED_RERANKER = create_reranker(settings)
    _SHARED_RERANKER_KEY = key
    return _SHARED_RERANKER


class _LazyEmbedder:
    """Delay sentence-transformers load until the first embed() call."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def embed(self, texts: list[str]) -> list[list[float]]:
        inner = _get_shared_embedder(self._settings)
        if inner is None:
            raise RuntimeError("embedding is disabled")
        return inner.embed(texts)


def build_orchestrator_deps(knowledge_base_id: str | None = None) -> OrchestratorDeps:
    settings = Settings()
    kb_id = knowledge_base_id or (LEGACY_PG_KB_ID if settings.use_pg else DEFAULT_IN_MEMORY_KB_ID)
    return _build_orchestrator_deps_for_kb(kb_id, settings)


def _build_orchestrator_deps_for_kb(knowledge_base_id: str, settings: Settings) -> OrchestratorDeps:
    kb = _resolve_kb(knowledge_base_id, settings)
    domain = load_domain(kb.domain_type)
    ontology = InMemoryOntology()
    domain.register_ontology(ontology)
    knowledge, graph, evidence, memory = _build_repos(knowledge_base_id, settings)
    embedder = _LazyEmbedder(settings) if settings.embedding_enabled else None
    embedding_store = None
    if settings.use_pg and embedder is not None:
        from infra.db import get_engine
        from akos.adapters.persistence.pg_embeddings import PgEmbeddingStore

        embedding_store = PgEmbeddingStore(
            get_engine(settings),
            knowledge_base_id,
            dims=settings.embedding_dims,
        )
    retrieval = HybridRetrieval(
        knowledge,
        graph,
        embedder=embedder,
        embedding_store=embedding_store,
    )
    retrieval.warm_index()
    chunk_retrieval = ChunkRetrieval(
        knowledge,
        embedder=embedder,
        embedding_store=embedding_store,
    )
    chunk_retrieval.warm_index()
    # Reranker weights are heavy; load on first Ask rerank, not on every admin page.
    reranker = None
    compiler = KnowledgeCompiler(ontology, knowledge, graph, evidence, domain.get_extractor(), retrieval)
    llm_client = OpenAiCompatibleClient(settings)
    wiki_retrieval: WikiPageRetrieval | None = None
    if settings.wiki_compile:
        wiki_retrieval = WikiPageRetrieval(llm_client=llm_client)
        wiki_root = compile_wiki_root(settings.data_root, knowledge_base_id)
        if wiki_root.is_dir():
            wiki_retrieval.index_wiki_root(wiki_root)
    evolution = EvolutionService(knowledge)
    verification = VerificationService()
    files = LocalFileStore(settings.data_root)
    if kb.domain_type == "ecommerce_cs":
        from akos.domains.ecommerce_cs.procedures import seed_ecommerce_procedures

        seed_ecommerce_procedures(memory)
    return OrchestratorDeps(
        files=files,
        knowledge=knowledge,
        ontology=ontology,
        graph=graph,
        evidence=evidence,
        compiler=compiler,
        llm_client=llm_client,
        retrieval=retrieval,
        chunk_retrieval=chunk_retrieval,
        memory=memory,
        domain=domain,
        evolution=evolution,
        verification=verification,
        knowledge_base_id=knowledge_base_id,
        wiki_retrieval=wiki_retrieval,
        reranker=reranker,
    )


def build_orchestrator_for_kb(
    knowledge_base_id: str,
    settings: Settings | None = None,
) -> LangGraphOrchestrator:
    resolved = settings or Settings()
    deps = _build_orchestrator_deps_for_kb(knowledge_base_id, resolved)
    return LangGraphOrchestrator(deps)


def build_default_orchestrator() -> LangGraphOrchestrator:
    settings = Settings()
    kb_id = LEGACY_PG_KB_ID if settings.use_pg else DEFAULT_IN_MEMORY_KB_ID
    return build_orchestrator_for_kb(kb_id)
