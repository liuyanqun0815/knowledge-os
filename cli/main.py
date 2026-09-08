import json

import typer

from infra.bootstrap import build_default_orchestrator

app = typer.Typer(help="AKOS — Agent-Native Knowledge Operating System")


@app.command()
def ingest(path: str, type: str = typer.Option("policy", "--type", help="Source type")) -> None:
    """Ingest a local file: register source and compile claims."""
    orchestrator = build_default_orchestrator()
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
    session_id: str = typer.Option("default", "--session-id", help="Session id for episodic memory"),
) -> None:
    """Ask a question against ingested knowledge."""
    orchestrator = build_default_orchestrator()
    answer = orchestrator.ask(question, session_id=session_id)
    typer.echo(
        json.dumps(
            {
                "text": answer.text,
                "claim_ids": answer.claim_ids,
                "evidence": answer.evidence,
                "confidence": answer.confidence,
                "retrieval_mode": answer.retrieval_mode,
            },
            ensure_ascii=False,
        )
    )


@app.command()
def inspect(claim_id: str) -> None:
    """Inspect evidence bound to a claim."""
    orchestrator = build_default_orchestrator()
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
