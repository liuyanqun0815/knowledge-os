from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from compiler.service import KnowledgeCompiler
from domains.base import DomainPort
from domains.registry import load_domain
from evolution.service import EvolutionService
from evidence.memory_repo import InMemoryEvidence
from evidence.ports import EvidencePort
from graph.memory_repo import InMemoryGraph
from graph.ports import GraphPort
from infra.files import LocalFileStore
from infra.llm import OpenAiCompatibleClient
from infra.pg_repos import PgKnowledge
from infra.settings import Settings
from knowledge.errors import DomainError
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.ports import KnowledgePort
from knowledge_base.models import KnowledgeBase
from memory.memory_repo import InMemoryMemoryStore
from memory.ports import MemoryPort
from ontology.registry import InMemoryOntology
from orchestrator.service import LangGraphOrchestrator
from retrieval.hybrid import HybridRetrieval
from verification.service import VerificationService

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
    memory: MemoryPort
    domain: DomainPort
    evolution: EvolutionService
    verification: VerificationService
    knowledge_base_id: str


def build_pg_knowledge(knowledge_base_id: str = LEGACY_PG_KB_ID) -> PgKnowledge:
    from infra.db import get_engine

    settings = Settings()
    return PgKnowledge(get_engine(settings), knowledge_base_id)


def _get_kb_repo(settings: Settings):
    if not settings.use_pg:
        return None
    from infra.db import get_engine
    from knowledge_base.pg_repo import PgKnowledgeBaseRepo

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
        from graph.adapters.neo4j import Neo4jGraph

        return Neo4jGraph(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
            knowledge_base_id=kb_id,
        )
    if backend == "postgres" and settings.use_pg and engine is not None:
        from infra.pg_graph import PgGraph

        return PgGraph(engine, kb_id)
    return InMemoryGraph()


def _build_repos(
    knowledge_base_id: str, settings: Settings
) -> tuple[KnowledgePort, GraphPort, EvidencePort, MemoryPort]:
    if settings.use_pg:
        from infra.db import get_engine
        from infra.pg_evidence import PgEvidence
        from infra.pg_memory import PgMemory

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
    retrieval = HybridRetrieval(knowledge, graph)
    compiler = KnowledgeCompiler(ontology, knowledge, graph, evidence, domain.get_extractor(), retrieval)
    llm_client = OpenAiCompatibleClient(settings)
    evolution = EvolutionService(knowledge)
    verification = VerificationService()
    files = LocalFileStore(settings.data_root)
    if kb.domain_type == "ecommerce_cs":
        from domains.ecommerce_cs.procedures import seed_ecommerce_procedures

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
        memory=memory,
        domain=domain,
        evolution=evolution,
        verification=verification,
        knowledge_base_id=knowledge_base_id,
    )


def build_orchestrator_for_kb(knowledge_base_id: str) -> LangGraphOrchestrator:
    settings = Settings()
    deps = _build_orchestrator_deps_for_kb(knowledge_base_id, settings)
    return LangGraphOrchestrator(deps)


def build_default_orchestrator() -> LangGraphOrchestrator:
    settings = Settings()
    kb_id = LEGACY_PG_KB_ID if settings.use_pg else DEFAULT_IN_MEMORY_KB_ID
    return build_orchestrator_for_kb(kb_id)
