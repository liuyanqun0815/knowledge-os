from typing import Protocol

from akos.domain.ports.compiler import CompileReport
from akos.domain.models.knowledge import Answer


class OrchestratorPort(Protocol):
    def register_source(self, file_path: str, source_type: str) -> str: ...

    def compile_source(self, source_id: str) -> CompileReport: ...

    def ingest(self, file_path: str, source_type: str) -> CompileReport: ...

    def ask(self, question: str, session_id: str | None = None) -> Answer: ...
