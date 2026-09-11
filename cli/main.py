import json
from enum import Enum

import typer

from infra.bootstrap import build_orchestrator_for_kb
from knowledge.lint import format_lint_report_human, lint_report_to_dict, run_lint
from wiki.export import export_wiki, resolve_wiki_output_dir, wiki_export_result_to_dict
from infra.settings import get_settings

app = typer.Typer(help="AKOS — Agent-Native Knowledge Operating System")


class LintOutputFormat(str, Enum):
    text = "text"
    json = "json"


@app.command()
def ingest(
    path: str,
    kb: str = typer.Option(..., "--kb", help="Knowledge base id"),
    type: str = typer.Option("policy", "--type", help="Source type"),
) -> None:
    """Ingest a local file: register source and compile claims."""
    orchestrator = build_orchestrator_for_kb(kb)
    report = orchestrator.ingest(path, type)
    typer.echo(
        json.dumps(
            {
                "source_id": report.source_id,
                "claims_created": report.claims_created,
                "entities_upserted": report.entities_upserted,
                "evidence_links": report.evidence_links,
                "quarantined": report.quarantined,
                "errors": report.errors,
            },
            ensure_ascii=False,
        )
    )


@app.command()
def ask(
    question: str,
    kb: str = typer.Option(..., "--kb", help="Knowledge base id"),
    session_id: str = typer.Option("default", "--session-id", help="Session id for episodic memory"),
) -> None:
    """Ask a question against ingested knowledge."""
    orchestrator = build_orchestrator_for_kb(kb)
    answer = orchestrator.ask(question, session_id=session_id)
    payload = {
        "text": answer.text,
        "claim_ids": answer.claim_ids,
        "chunk_ids": answer.chunk_ids,
        "evidence": answer.evidence,
        "chunk_citations": answer.chunk_citations,
        "synthesis_used": answer.synthesis_used,
        "confidence": answer.confidence,
        "retrieval_mode": answer.retrieval_mode,
        "verification_status": answer.verification_status,
        "competing_claim_ids": answer.competing_claim_ids,
        "procedure_id": answer.procedure_id,
    }
    if answer.as_of is not None:
        payload["as_of"] = answer.as_of.isoformat()
    typer.echo(json.dumps(payload, ensure_ascii=False))


@app.command("lint")
def lint_kb(
    kb: str = typer.Option(..., "--kb", help="Knowledge base id"),
    output_format: LintOutputFormat = typer.Option(
        LintOutputFormat.text,
        "--format",
        help="Output format: text or json",
    ),
) -> None:
    """Scan a knowledge base for conflicts, missing evidence, and other health issues."""
    orchestrator = build_orchestrator_for_kb(kb)
    report = run_lint(orchestrator.deps.knowledge, orchestrator.deps.evidence, kb)
    if output_format == LintOutputFormat.json:
        typer.echo(json.dumps(lint_report_to_dict(report), ensure_ascii=False))
        return
    typer.echo(format_lint_report_human(report))


@app.command("wiki-export")
def wiki_export(
    kb: str = typer.Option(..., "--kb", help="Knowledge base id"),
    out: str | None = typer.Option(None, "--out", help="Output directory (default: {data_root}/{kb}/wiki/)"),
    with_llm_summaries: bool = typer.Option(False, "--with-llm-summaries", help="Generate LLM summaries"),
) -> None:
    """Export active claims as Obsidian-friendly markdown wiki pages."""
    from pathlib import Path

    settings = get_settings()
    orchestrator = build_orchestrator_for_kb(kb)
    if out:
        output_dir = Path(out)
    else:
        output_dir = Path(settings.data_root) / kb / "wiki"
    result = export_wiki(
        orchestrator.deps.knowledge,
        orchestrator.deps.evidence,
        kb,
        output_dir,
        use_llm=with_llm_summaries or settings.wiki_llm,
        llm_client=orchestrator.deps.llm_client,
        settings=settings,
        graph=orchestrator.deps.graph,
    )
    typer.echo(json.dumps(wiki_export_result_to_dict(result), ensure_ascii=False))


@app.command()
def inspect(
    claim_id: str,
    kb: str = typer.Option(..., "--kb", help="Knowledge base id"),
) -> None:
    """Inspect evidence bound to a claim."""
    orchestrator = build_orchestrator_for_kb(kb)
    bundle = orchestrator.deps.evidence.explain([claim_id])
    typer.echo(
        json.dumps(
            {
                "conclusion": bundle.conclusion,
                "items": bundle.items,
                "confidence": bundle.confidence,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    app()
