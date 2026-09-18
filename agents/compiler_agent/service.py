from akos.domain.ports.compiler import CompileReport, CompilerPort


def ingest(compiler: CompilerPort, source_id: str, staging: bool = False) -> CompileReport:
    return compiler.ingest(source_id, staging=staging)
