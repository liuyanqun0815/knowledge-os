from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    monkeypatch.setenv("AKOS_SOURCE_CONTENT_MAX_BYTES", "64")
    return TestClient(create_app(data_root=str(tmp_path / "data")))


def test_get_source_content_returns_utf8_text(client: TestClient) -> None:
    upload = client.post(
        "/admin/knowledge-bases/preview-kb/sources/upload-tree",
        files=[("files", ("guide.md", "# 指南\n欢迎。", "text/markdown"))],
        data={"relative_paths": ["docs/guide.md"]},
    )
    assert upload.status_code == 200
    source_id = upload.json()["results"][0]["source_id"]

    response = client.get(f"/admin/knowledge-bases/preview-kb/sources/{source_id}/content")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_id"] == source_id
    assert payload["relative_path"] == "docs/guide.md"
    assert payload["content"] == "# 指南\n欢迎。"
    assert payload["encoding"] == "utf-8"
    assert payload["size_bytes"] == len("# 指南\n欢迎。".encode("utf-8"))


def test_get_source_content_rejects_oversized_file(client: TestClient, tmp_path: Path) -> None:
    big = "x" * 80
    upload = client.post(
        "/admin/knowledge-bases/preview-kb/sources/upload-tree",
        files=[("files", ("big.md", big, "text/markdown"))],
        data={"relative_paths": ["big.md"]},
    )
    source_id = upload.json()["results"][0]["source_id"]

    response = client.get(f"/admin/knowledge-bases/preview-kb/sources/{source_id}/content")
    assert response.status_code == 413
    assert "source_content_too_large" in response.json()["detail"]


def test_get_source_content_missing_file_returns_404(client: TestClient, tmp_path: Path) -> None:
    upload = client.post(
        "/admin/knowledge-bases/preview-kb/sources/upload-tree",
        files=[("files", ("gone.md", "temp", "text/markdown"))],
        data={"relative_paths": ["gone.md"]},
    )
    source_id = upload.json()["results"][0]["source_id"]
    (tmp_path / "data" / "preview-kb" / "gone.md").unlink()

    response = client.get(f"/admin/knowledge-bases/preview-kb/sources/{source_id}/content")
    assert response.status_code == 404
    assert "source_file_not_found" in response.json()["detail"]
