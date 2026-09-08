from dataclasses import dataclass

from compiler.rule_extractor import RuleExtractor
from compiler.service import KnowledgeCompiler
from domains.ecommerce_cs.seed import register_ecommerce_cs
from evidence.memory_repo import InMemoryEvidence
from graph.memory_repo import InMemoryGraph
from infra.files import LocalFileStore
from knowledge.memory_repo import InMemoryKnowledge
from memory.memory_repo import InMemoryMemoryStore
from ontology.registry import InMemoryOntology
from orchestrator.service import LangGraphOrchestrator
from retrieval.hybrid import HybridRetrieval


@dataclass
class OrchestratorDeps:
    files: LocalFileStore
    knowledge: InMemoryKnowledge
    ontology: InMemoryOntology
    graph: InMemoryGraph
    evidence: InMemoryEvidence
    compiler: KnowledgeCompiler
    retrieval: HybridRetrieval
    memory: InMemoryMemoryStore


def build_orchestrator_deps() -> OrchestratorDeps:
    ontology = InMemoryOntology()
    register_ecommerce_cs(ontology)
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    retrieval = HybridRetrieval(knowledge, graph)
    compiler = KnowledgeCompiler(ontology, knowledge, graph, evidence, RuleExtractor(), retrieval)
    memory = InMemoryMemoryStore()
    files = LocalFileStore()
    return OrchestratorDeps(
        files=files,
        knowledge=knowledge,
        ontology=ontology,
        graph=graph,
        evidence=evidence,
        compiler=compiler,
        retrieval=retrieval,
        memory=memory,
    )


def build_default_orchestrator() -> LangGraphOrchestrator:
    return LangGraphOrchestrator(build_orchestrator_deps())
