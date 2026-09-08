from typing import Protocol

from compiler.ports import CompileReport
from knowledge.models import Answer


class OrchestratorPort(Protocol):
    def register_source(self, file_path: str, source_type: str) -> str: ...

    def compile_source(self, source_id: str) -> CompileReport: ...

    def ingest(self, file_path: str, source_type: str) -> CompileReport: ...

    def ask(self, question: str, session_id: str | None = None) -> Answer: ...
