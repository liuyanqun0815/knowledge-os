from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient

from app.main import create_app
from infra.bootstrap import DEFAULT_IN_MEMORY_KB_ID
from wiki.paths import compile_wiki_root


def test_admin_wiki_download_returns_zip(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    wiki_root = compile_wiki_root(tmp_path, kb_id)
    (wiki_root / "售后").mkdir(parents=True)
    (wiki_root / "index.md").write_text("# index\n", encoding="utf-8")
    (wiki_root / "售后" / "退货.md").write_text("# 退货\n", encoding="utf-8")

    response = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/download")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert "attachment" in response.headers["content-disposition"]
    assert f"{kb_id}-wiki.zip" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
    assert "index.md" in names
    assert "售后/退货.md" in names


def test_admin_wiki_download_404_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = DEFAULT_IN_MEMORY_KB_ID

    response = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/download")
    assert response.status_code == 404
    assert response.json()["detail"] == "wiki_not_found"
