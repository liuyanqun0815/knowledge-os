from fastapi.testclient import TestClient

from app.main import create_app
from wiki.meta import WikiPageMeta, save_pages_meta
from wiki.paths import compile_wiki_root


def test_wiki_tree_and_page_and_search(tmp_path, monkeypatch):
    monkeypatch.delenv("ADMIN_API_TOKEN", raising=False)
    monkeypatch.setenv("AKOS_USE_PG", "false")
    client = TestClient(create_app(data_root=str(tmp_path)))
    kb_id = "legacy"
    wiki = compile_wiki_root(tmp_path, kb_id)
    (wiki / "售后").mkdir(parents=True)
    (wiki / "售后" / "退款到账时效.md").write_text("# 退款\n\n退款时效说明\n", encoding="utf-8")
    save_pages_meta(
        wiki,
        {
            "售后/退款到账时效": WikiPageMeta(
                path="售后/退款到账时效.md",
                title="退款到账时效",
                kind="source_page",
                content_hash="x",
                source_ids=["s"],
                hub="售后",
                summary="退款时效说明",
            )
        },
    )

    tree = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/tree")
    assert tree.status_code == 200
    assert tree.json()["hubs"][0]["pages"][0]["page_id"] == "售后/退款到账时效"

    page = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/pages/售后/退款到账时效")
    assert page.status_code == 200
    assert "退款时效说明" in page.json()["markdown"]

    search = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/search", params={"q": "退款"})
    assert search.status_code == 200
    assert search.json()["total"] >= 1

    bad = client.get(f"/admin/knowledge-bases/{kb_id}/wiki/pages/../secrets")
    assert bad.status_code in {400, 404}
