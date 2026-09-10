from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    return TestClient(create_app(data_root=str(tmp_path / "data")))


def _upload_tree(client: TestClient, kb_id: str, entries: list[tuple[str, str]]):
    return client.post(
        f"/admin/knowledge-bases/{kb_id}/sources/upload-tree",
        files=[("files", (Path(path).name, content, "text/markdown")) for path, content in entries],
        data={"relative_paths": [path for path, _ in entries]},
    )


def test_upload_tree_preserves_nested_paths(client: TestClient, tmp_path: Path) -> None:
    response = _upload_tree(
        client,
        "tree-kb",
        [
            ("policies/refund.md", "# 退款\n七天内可退款。"),
            ("guides/start.txt", "开始使用。"),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload_mode"] == "tree"
    assert payload["files_ingested"] == 2
    assert {item["relative_path"] for item in payload["results"]} == {
        "policies/refund.md",
        "guides/start.txt",
    }
    assert (tmp_path / "data" / "tree-kb" / "policies" / "refund.md").exists()
    assert (tmp_path / "data" / "tree-kb" / "guides" / "start.txt").exists()


def test_upload_tree_rejects_mismatched_or_unsafe_paths(client: TestClient) -> None:
    mismatched = client.post(
        "/admin/knowledge-bases/tree-kb/sources/upload-tree",
        files=[("files", ("one.md", "# one", "text/markdown"))],
        data={"relative_paths": ["one.md", "two.md"]},
    )
    unsafe = _upload_tree(client, "tree-kb", [("../outside.md", "# outside")])

    assert mismatched.status_code == 400
    assert unsafe.status_code == 400


def test_single_upload_accepts_relative_path(client: TestClient, tmp_path: Path) -> None:
    response = client.post(
        "/admin/knowledge-bases/single-kb/sources/upload",
        files={"file": ("guide.md", "# 指南", "text/markdown")},
        data={"relative_path": "docs/guide.md"},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["relative_path"] == "docs/guide.md"
    assert (tmp_path / "data" / "single-kb" / "docs" / "guide.md").exists()


def test_move_file_keeps_source_id_stable(client: TestClient, tmp_path: Path) -> None:
    upload = _upload_tree(client, "move-kb", [("a/guide.md", "# 指南")])
    source_id = upload.json()["results"][0]["source_id"]

    response = client.post(
        "/admin/knowledge-bases/move-kb/sources/move",
        json={"from_path": "a/guide.md", "to_path": "c/renamed.md"},
    )

    assert response.status_code == 200
    item = response.json()[0]
    assert item["id"] == source_id
    assert item["relative_path"] == "c/renamed.md"
    assert item["title"] == "renamed.md"
    assert not (tmp_path / "data" / "move-kb" / "a" / "guide.md").exists()
    assert (tmp_path / "data" / "move-kb" / "c" / "renamed.md").exists()


def test_move_directory_moves_all_sources_and_rejects_conflicts(client: TestClient) -> None:
    _upload_tree(
        client,
        "move-dir-kb",
        [
            ("a/one.md", "# one"),
            ("a/nested/two.md", "# two"),
            ("existing.md", "# existing"),
        ],
    )

    response = client.post(
        "/admin/knowledge-bases/move-dir-kb/sources/move",
        json={"from_path": "a/", "to_path": "archive/"},
    )
    conflict = client.post(
        "/admin/knowledge-bases/move-dir-kb/sources/move",
        json={"from_path": "archive/one.md", "to_path": "existing.md"},
    )

    assert response.status_code == 200
    assert {item["relative_path"] for item in response.json()} == {
        "archive/one.md",
        "archive/nested/two.md",
    }
    assert conflict.status_code == 409


def test_delete_file_removes_disk_and_source(client: TestClient, tmp_path: Path) -> None:
    upload = _upload_tree(client, "delete-kb", [("docs/guide.md", "# 指南")])
    source_id = upload.json()["results"][0]["source_id"]

    response = client.delete(f"/admin/knowledge-bases/delete-kb/sources/{source_id}")

    assert response.status_code == 204
    assert not (tmp_path / "data" / "delete-kb" / "docs" / "guide.md").exists()
    assert client.get("/admin/knowledge-bases/delete-kb/sources").json() == []


def test_delete_tree_removes_directory_sources(client: TestClient, tmp_path: Path) -> None:
    _upload_tree(
        client,
        "delete-tree-kb",
        [
            ("policies/one.md", "# one"),
            ("policies/nested/two.md", "# two"),
            ("keep.md", "# keep"),
        ],
    )

    response = client.post(
        "/admin/knowledge-bases/delete-tree-kb/sources/delete-tree",
        json={"path": "policies/"},
    )

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 2
    remaining = client.get("/admin/knowledge-bases/delete-tree-kb/sources").json()
    assert [item["relative_path"] for item in remaining] == ["keep.md"]
    assert not (tmp_path / "data" / "delete-tree-kb" / "policies").exists()
