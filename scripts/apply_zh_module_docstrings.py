"""一次性脚本：将模块首行 docstring 替换为中文（维护时可删）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS: dict[str, str] = {
    "akos/__init__.py": "AKOS 包根（六边形分层）。",
    "akos/application/__init__.py": "应用用例层。",
    "akos/domain/__init__.py": "领域层：模型与端口（不含 IO 适配器）。",
    "akos/domain/models/__init__.py": "领域模型（Claim、Source、KnowledgeBase 等）。",
    "akos/adapters/__init__.py": "IO 适配器，实现领域端口。",
    "akos/adapters/files/__init__.py": "文件存储适配器。",
    "akos/adapters/graph/__init__.py": "图存储适配器（如 Neo4j）。",
    "akos/adapters/llm/__init__.py": "LLM 客户端适配器。",
    "akos/adapters/ontology/__init__.py": "本体适配器。",
    "akos/adapters/persistence/__init__.py": "持久化适配器（内存与 PostgreSQL）。",
    "akos/adapters/retrieval/__init__.py": "检索 / 向量 / 重排适配器。",
    "akos/domains/__init__.py": "领域插件（如 ecommerce_cs、loan_finance）。",
    "akos/interfaces/__init__.py": "AKOS 接口层（HTTP API）。",
    "akos/interfaces/api/__init__.py": "HTTP API（FastAPI 应用与管理路由）。",
    "akos/application/topics/__init__.py": "主题聚类用例。",
    "akos/application/lint/__init__.py": "知识库 Lint 用例。",
    "akos/application/wiki/__init__.py": "Wiki：由 Claim 等编译为 Markdown 并导出。",
    "akos/application/wiki/related.py": "Wiki 跨页 wikilink 推荐与注入。",
    "akos/application/wiki/layout.py": "Wiki 目录分类与单页/多页拆分启发式。",
    "akos/application/wiki/hierarchy.py": "主题层级映射：hub / leaf / snippet。",
    "akos/application/wiki/source_plan.py": "以源文档为中心的 Wiki 编译：LLM 规划页面。",
    "akos/adapters/graph/noop.py": "graph_enabled=false 时使用的空实现 GraphPort。",
    "akos/domains/ecommerce_cs/wiki_hierarchy.py": "电商客服 Wiki 层级种子映射。",
    "infra/doc_extract.py": "从 Office/PDF 等上传文件提取纯文本供入库。",
}


def _replace_leading_docstring(path: Path, zh: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if not text.startswith('"""'):
        return False
    end = text.find('"""', 3)
    if end < 0:
        return False
    rest = text[end + 3 :]
    if rest.startswith("\n"):
        rest = rest[1:]
    path.write_text(f'"""{zh}"""\n' + rest, encoding="utf-8")
    return True


def main() -> None:
    for rel, zh in REPLACEMENTS.items():
        path = ROOT / rel
        if not path.is_file():
            print("skip missing", rel)
            continue
        if _replace_leading_docstring(path, zh):
            print("ok", rel)
        else:
            print("skip", rel)

    ports = ROOT / "akos/domain/ports/__init__.py"
    ports.write_text(
        '"""领域端口包。\n\n'
        "请直接导入具体模块，例如::\n\n"
        "    from akos.domain.ports.knowledge import KnowledgePort\n\n"
        "勿在此做 barrel 重导出，以免与 legacy shim 循环依赖。\n"
        '"""\n',
        encoding="utf-8",
    )
    print("ok akos/domain/ports/__init__.py")


if __name__ == "__main__":
    main()
