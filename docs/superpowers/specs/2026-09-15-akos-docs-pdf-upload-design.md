# AKOS 文档上传扩展：PDF / DOCX / DOC + RapidOCR

**日期**: 2026-09-15  
**状态**: 已确认  
**依赖**: 现有上传 → `LocalFileStore` / `orchestrator.ingest`（仅 UTF-8 `.md`/`.txt`）

---

## 1. 动机

管理台上传仅支持 `.md` / `.txt` / `.zip`。业务侧常见 `.pdf` / `.docx` / 旧版 `.doc`，需在入库前抽出文本再走现有 Claim 编译链路。扫描件 PDF 需 OCR。

---

## 2. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | 解析路线 | 上传后抽文本 → 落盘同名 `.md` → 现有 ingest |
| 2 | PDF | 先文字层；为空则渲染页图 + **RapidOCR** |
| 3 | DOCX | `python-docx` |
| 4 | DOC（旧二进制） | **尽力**：有 LibreOffice/`soffice` 则转 txt；否则 400 提示另存为 docx |
| 5 | OCR 引擎 | RapidOCR（onnxruntime） |
| 6 | 依赖 | optional extra `akos[docs]` |
| 7 | 原件 | 保留在 KB 目录；ingest 目标为派生 `.md` |

---

## 3. 数据流

```text
upload (.pdf|.docx|.doc|.md|.txt|.zip)
  → 校验白名单
  → 写入原路径（二进制原件或纯文本）
  → 若为可抽取类型：extract → {stem}.md（UTF-8）
  → ingest({stem}.md)   # LocalFileStore 仍只读 md/txt
```

ZIP 内成员同样：允许后缀含 pdf/docx/doc；抽取后对每个派生 md 调用 ingest。

---

## 4. 模块

| 模块 | 职责 |
|------|------|
| `infra/doc_extract.py` | `extract_document(path) -> str`；按后缀分流；OCR 懒加载 |
| `infra/upload_utils.py` | 扩展 `ALLOWED_UPLOAD_SUFFIXES`；区分文本/可抽取二进制 |
| `admin_api/routes_sources.py` | 上传/树/ZIP 保存后调用抽取再 ingest |
| `web` SourcesPage | accept / 校验文案 |

失败：抽不出有效文本（空白）→ HTTP 400，`detail` 含原因。

---

## 5. 非目标

- 不在问答时实时解析 PDF  
- 不改 Claim/检索语义  
- 不保证所有旧 `.doc` 可解析  
- 不做云 OCR  

---

## 6. 测试

- 单元：docx/pdf 文字层 fixture → 非空文本  
- PDF 空文字层：mock OCR 返回字样  
- DOC：无 soffice 时返回明确错误  
- API：上传假 pdf/docx 成功产生 `.md` 且 list sources 可见  
