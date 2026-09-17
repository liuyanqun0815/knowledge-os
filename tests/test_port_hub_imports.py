def test_knowledge_port_importable_from_hub_and_shim():
    from akos.domain.ports.knowledge import KnowledgePort as Hub
    from knowledge.ports import KnowledgePort as Shim

    assert Hub is Shim


def test_storage_and_ontology_ports_hub_identity():
    from akos.domain.ports.evidence import EvidencePort as EvidenceHub
    from akos.domain.ports.graph import GraphPort as GraphHub
    from akos.domain.ports.knowledge_base import KnowledgeBasePort as KbHub
    from akos.domain.ports.memory import MemoryPort as MemoryHub
    from akos.domain.ports.ontology import OntologyPort as OntologyHub
    from evidence.ports import EvidencePort as EvidenceShim
    from graph.ports import GraphPort as GraphShim
    from knowledge_base.ports import KnowledgeBasePort as KbShim
    from memory.ports import MemoryPort as MemoryShim
    from ontology.ports import OntologyPort as OntologyShim

    assert EvidenceHub is EvidenceShim
    assert GraphHub is GraphShim
    assert MemoryHub is MemoryShim
    assert OntologyHub is OntologyShim
    assert KbHub is KbShim


def test_compiler_and_retrieval_ports_hub_identity():
    from akos.domain.ports.compiler import CompileReport as ReportHub
    from akos.domain.ports.compiler import ExtractorPort as ExtractorHub
    from akos.domain.ports.retrieval import Hit as HitHub
    from akos.domain.ports.retrieval import RetrievalMode as ModeHub
    from akos.domain.ports.retrieval import RetrievalPort as RetrievalHub
    from compiler.ports import CompileReport as ReportShim
    from compiler.ports import ExtractorPort as ExtractorShim
    from retrieval.ports import Hit as HitShim
    from retrieval.ports import RetrievalMode as ModeShim
    from retrieval.ports import RetrievalPort as RetrievalShim

    assert ExtractorHub is ExtractorShim
    assert ReportHub is ReportShim
    assert HitHub is HitShim
    assert ModeHub is ModeShim
    assert RetrievalHub is RetrievalShim


def test_evolution_verification_orchestrator_hub_identity():
    from akos.domain.ports.evolution import EvolutionPort as EvolutionHub
    from akos.domain.ports.orchestrator import OrchestratorPort as OrchHub
    from akos.domain.ports.verification import VerificationResult as VerificationHub
    from evolution.ports import EvolutionPort as EvolutionShim
    from orchestrator.ports import OrchestratorPort as OrchShim
    from verification.ports import VerificationResult as VerificationShim

    assert EvolutionHub is EvolutionShim
    assert VerificationHub is VerificationShim
    assert OrchHub is OrchShim


def test_domain_port_hub_identity():
    from akos.domain.ports.domain import DomainPort as Hub
    from domains.base import DomainPort as Shim

    assert Hub is Shim
