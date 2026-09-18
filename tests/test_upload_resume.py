def test_resume_processes_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)

    from akos.interfaces.api.main import create_app
    from infra.bootstrap import build_orchestrator_for_kb
    from akos.interfaces.api.admin_api.upload_jobs import register_pending_source, resume_incomplete_uploads

    app = create_app(data_root=str(tmp_path))
    kb_id = "kb1"
    orch = build_orchestrator_for_kb(kb_id, settings=app.state.settings)
    app.state.orchestrator_cache[kb_id] = orch
    kb_dir = tmp_path / kb_id
    kb_dir.mkdir(parents=True)
    original = kb_dir / "x.md"
    original.write_text("七天无理由适用类目为非定制商品。", encoding="utf-8")
    register_pending_source(
        knowledge=orch.deps.knowledge,
        kb_dir=kb_dir,
        original=original,
        source_type="policy",
    )
    resume_incomplete_uploads(app)
    src = orch.deps.knowledge.get_source("x")
    assert src is not None
    assert src.status != "pending"
