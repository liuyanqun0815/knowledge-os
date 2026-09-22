"""检查 akos/、infra/ 中 logging 首参是否仍为纯英文（约定应使用中文）。"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (ROOT / "akos", ROOT / "infra")
SKIP_PARTS = {"tests", "__pycache__", ".venv"}

# 允许保留英文的日志前缀（机器字段、已有约定）
ALLOW_PREFIXES = (
    "akos.",
    "HTTP",
    "API",
    "JSON",
    "LLM Claim",  # 技术缩写组合
)

# 明显以英文句子开头的模式
ENGLISH_START = re.compile(
    r"^[A-Za-z][a-z]+(\s+[a-z]+|\s+failed|\s+missing|\s+disabled|\s+call|\s+for\s)",
)


def _is_probably_english_message(msg: str) -> bool:
    s = msg.strip()
    if not s:
        return False
    if any("\u4e00" <= ch <= "\u9fff" for ch in s):
        return False
    if any(s.startswith(p) for p in ALLOW_PREFIXES):
        return False
    return bool(ENGLISH_START.match(s)) or s.split()[0].isascii() and len(s.split()) >= 3


class _LogVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.hits: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = ""
        if isinstance(func, ast.Attribute):
            name = func.attr
        if name in {"debug", "info", "warning", "error", "exception", "critical"} and node.args:
            arg0 = node.args[0]
            if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                text = arg0.value
                if _is_probably_english_message(text):
                    self.hits.append((node.lineno, text))
        self.generic_visit(node)


def main() -> int:
    problems: list[str] = []
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError:
                continue
            visitor = _LogVisitor(path)
            visitor.visit(tree)
            for line, msg in visitor.hits:
                rel = path.relative_to(ROOT)
                problems.append(f"{rel}:{line}: {msg[:80]!r}")

    if problems:
        print("发现疑似英文 logging 文案（请改为中文，见 docs/conventions/zh-remarks.md）：")
        for item in problems[:50]:
            print(" ", item)
        if len(problems) > 50:
            print(f"  ... 另有 {len(problems) - 50} 条")
        return 1
    print("未发现疑似英文 logging 首参。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
