from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from wiki.archive import build_wiki_zip


def test_build_wiki_zip_preserves_tree_structure(tmp_path: Path):
    wiki_root = tmp_path / "wiki"
    (wiki_root / "售后").mkdir(parents=True)
    (wiki_root / "index.md").write_text("# 总览\n", encoding="utf-8")
    (wiki_root / "售后" / "七天无理由退货.md").write_text("# 退货\n", encoding="utf-8")
    (wiki_root / ".meta").mkdir()
    (wiki_root / ".meta" / "pages.json").write_text("{}", encoding="utf-8")

    payload = build_wiki_zip(wiki_root)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
    assert "index.md" in names
    assert "售后/七天无理由退货.md" in names
    assert ".meta/pages.json" in names


def test_build_wiki_zip_requires_directory(tmp_path: Path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        build_wiki_zip(missing)
