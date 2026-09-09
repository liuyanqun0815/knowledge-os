import json

import typer

from infra.bootstrap import build_orchestrator_for_kb

app = typer.Typer(help="AKOS — Agent-Native Knowledge Operating System")


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
        "evidence": answer.evidence,
        "confidence": answer.confidence,
        "retrieval_mode": answer.retrieval_mode,
        "verification_status": answer.verification_status,
        "competing_claim_ids": answer.competing_claim_ids,
        "procedure_id": answer.procedure_id,
    }
    if answer.as_of is not None:
        payload["as_of"] = answer.as_of.isoformat()
    typer.echo(json.dumps(payload, ensure_ascii=False))


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
