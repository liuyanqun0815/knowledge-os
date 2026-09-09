from dataclasses import replace
from datetime import datetime

from compiler.ports import CompileReport
from evolution.ports import ApplyReport
from knowledge.errors import DomainError
from knowledge.models import Answer
from orchestrator.graphs.ask_graph import build_ask_graph
from orchestrator.graphs.ingest_graph import build_ingest_graph


class LangGraphOrchestrator:
    def __init__(self, deps) -> None:
        self.deps = deps
        self._ingest = build_ingest_graph(deps)
        self._ask = build_ask_graph(deps)

    def register_source(
        self,
        file_path: str,
        source_type: str,
        replaces_source_id: str | None = None,
    ) -> str:
        stored = self.deps.files.store(file_path, source_type)
        source = stored.source
        if replaces_source_id:
            source = replace(source, replaces_source_id=replaces_source_id)
        source = self.deps.knowledge.save_source(source)
        self.deps.knowledge.save_source_text(source.id, stored.text)
        return source.id

    def compile_source(self, source_id: str) -> CompileReport:
        source = self.deps.knowledge.get_source(source_id)
        staging = bool(source and source.replaces_source_id)
        return self.deps.compiler.ingest(source_id, staging=staging)

    def evolve_source(self, new_source_id: str, replaces_source_id: str | None = None) -> ApplyReport:
        new_source = self.deps.knowledge.get_source(new_source_id)
        if new_source is None:
            raise DomainError(f"source_not_found: {new_source_id}")

        old_source_id = replaces_source_id or new_source.replaces_source_id
        if not old_source_id:
            raise DomainError("missing replaces_source_id for evolve")

        old_source = self.deps.knowledge.get_source(old_source_id)
        if old_source is None:
            raise DomainError(f"source_not_found: {old_source_id}")

        staging_claims = [
            claim
            for claim in self.deps.knowledge.get_claims_for_source(new_source_id)
            if claim.status == "staging"
        ]
        if not staging_claims:
            self.deps.compiler.ingest(new_source_id, staging=True)

        diff = self.deps.evolution.diff_sources(old_source_id, new_source_id)
        report = self.deps.evolution.apply_diff(diff)
        for claim_id in report.claims_activated:
            claim = self.deps.knowledge.get_claim(claim_id)
            if claim is not None:
                self.deps.retrieval.index_claim(claim)
        return report

    def ingest(
        self,
        file_path: str,
        source_type: str,
        replaces_source_id: str | None = None,
    ) -> CompileReport:
        state = self._ingest.invoke(
            {
                "file_path": file_path,
                "source_type": source_type,
                "source_id": None,
                "replaces_source_id": replaces_source_id,
                "report": None,
                "verify_report": None,
                "evolve_report": None,
                "error": None,
            }
        )
        return state["report"]

    def ask(self, question: str, session_id: str | None = None, as_of: datetime | None = None) -> Answer:
        state = self._ask.invoke(
            {
                "question": question,
                "session_id": session_id,
                "as_of": as_of,
                "normalized_question": None,
                "retrieval_mode": None,
                "hits": [],
                "claim_ids": [],
                "verification": None,
                "trace": [],
                "answer": None,
            }
        )
        return state["answer"]
