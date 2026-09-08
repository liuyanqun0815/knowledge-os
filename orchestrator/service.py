from compiler.ports import CompileReport
from knowledge.models import Answer
from orchestrator.graphs.ask_graph import build_ask_graph
from orchestrator.graphs.ingest_graph import build_ingest_graph


class LangGraphOrchestrator:
    def __init__(self, deps) -> None:
        self.deps = deps
        self._ingest = build_ingest_graph(deps)
        self._ask = build_ask_graph(deps)

    def register_source(self, file_path: str, source_type: str) -> str:
        stored = self.deps.files.store(file_path, source_type)
        source = self.deps.knowledge.save_source(stored.source)
        self.deps.knowledge.save_source_text(source.id, stored.text)
        return source.id

    def compile_source(self, source_id: str) -> CompileReport:
        return self.deps.compiler.ingest(source_id)

    def ingest(self, file_path: str, source_type: str) -> CompileReport:
        state = self._ingest.invoke(
            {
                "file_path": file_path,
                "source_type": source_type,
                "source_id": None,
                "report": None,
                "error": None,
            }
        )
        return state["report"]

    def ask(self, question: str, session_id: str | None = None) -> Answer:
        state = self._ask.invoke(
            {
                "question": question,
                "session_id": session_id,
                "normalized_question": None,
                "retrieval_mode": None,
                "hits": [],
                "claim_ids": [],
                "answer": None,
            }
        )
        return state["answer"]
