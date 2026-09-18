"""Hub import smoke after Phase 5 shim removal."""


def test_domain_ports_importable():
    from akos.domain.ports.compiler import CompileReport, ExtractorPort
    from akos.domain.ports.domain import DomainPort
    from akos.domain.ports.evidence import EvidencePort
    from akos.domain.ports.evolution import EvolutionPort
    from akos.domain.ports.graph import GraphPort
    from akos.domain.ports.knowledge import KnowledgePort
    from akos.domain.ports.knowledge_base import KnowledgeBasePort
    from akos.domain.ports.memory import MemoryPort
    from akos.domain.ports.ontology import OntologyPort
    from akos.domain.ports.orchestrator import OrchestratorPort
    from akos.domain.ports.retrieval import Hit, RetrievalMode, RetrievalPort
    from akos.domain.ports.verification import VerificationResult

    assert all(
        x is not None
        for x in (
            KnowledgePort,
            EvidencePort,
            GraphPort,
            MemoryPort,
            OntologyPort,
            KnowledgeBasePort,
            ExtractorPort,
            CompileReport,
            Hit,
            RetrievalMode,
            RetrievalPort,
            EvolutionPort,
            VerificationResult,
            OrchestratorPort,
            DomainPort,
        )
    )


def test_adapter_hub_importable():
    from akos.adapters.files.local import LocalFileStore
    from akos.adapters.llm.client import OpenAiCompatibleClient
    from akos.adapters.persistence.knowledge_memory import InMemoryKnowledge
    from akos.adapters.persistence.pg_knowledge import PgKnowledge
    from akos.adapters.retrieval.hybrid import HybridRetrieval

    assert all(
        x is not None
        for x in (InMemoryKnowledge, PgKnowledge, OpenAiCompatibleClient, LocalFileStore, HybridRetrieval)
    )


def test_application_hub_importable():
    from akos.application.ask.synthesis import build_synthesis_context
    from akos.application.evolution.service import EvolutionService
    from akos.application.ingest.service import KnowledgeCompiler
    from akos.application.wiki.compile import compile_topics_for_source
    from akos.interfaces.api.main import create_app

    assert all(
        x is not None
        for x in (compile_topics_for_source, KnowledgeCompiler, EvolutionService, build_synthesis_context, create_app)
    )
