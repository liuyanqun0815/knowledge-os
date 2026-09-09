from compiler.ports import CompileReport, CompilerPort


def ingest(compiler: CompilerPort, source_id: str, staging: bool = False) -> CompileReport:
    return compiler.ingest(source_id, staging=staging)
