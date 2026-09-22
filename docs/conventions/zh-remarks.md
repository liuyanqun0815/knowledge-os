# 中文备注约定

与 `.cursor/rules/chinese-remarks.mdc` 一致，供贡献者阅读。

- **注释 / docstring / 日志**：简体中文（`akos/`、`infra/`、`web/src/` 业务代码）
- **标识符 / pytest 函数名 / 外部 API 字段名**：英文
- **入库日志**：`akos.ingest.flow`，前缀 `入库·`、`上传任务`、`混合抽取`
- **自检**：`uv run python scripts/check_english_remarks.py`（扫描 logging 首参）
- **批量模块 docstring**：`uv run python scripts/apply_zh_module_docstrings.py`（维护列表，按需扩展）
