# AKOS 全部上传异步化

**日期**: 2026-09-15  
**状态**: 已确认  
**依赖**:
- 文档抽取：`docs/superpowers/specs/2026-09-15-akos-docs-pdf-upload-design.md`
- Source 状态 / LLM 补抽：`docs/superpowers/specs/2026-09-09-akos-hybrid-llm-extraction-design.md`

---

## 1. 动机

上传路径（含 `.md`/`.txt` 与 PDF/DOCX 抽取、`orchestrator.ingest`）目前在 HTTP 请求内同步执行，会占用 FastAPI 事件循环与 worker，拖慢同进程 Ask / 列表等接口。LLM enrich 已用 `BackgroundTasks`；需把「落盘之后的编译链路」也挪出请求关键路径。

---

## 2. 已确认决策

| # | 决策 | 选择 |
|---|------|------|
| 1 | 范围 | **所有**上传异步：单文件 / ZIP / upload-tree，含 `.md` `.txt` `.pdf` `.docx` `.doc` |
| 2 | 请求内职责 | 仅：白名单校验、写盘（ZIP 解压）、预登记 `Source(pending)`、调度后台任务 |
| 3 | HTTP | 成功接收 → **202**；校验/写盘失败仍 **400/4xx** |
| 4 | 响应体 | 沿用 `SourceUploadResponse`，新增 `accepted_async: bool`（成功接收时为 `true`） |
| 5 | 后台执行 | 进程内 `BackgroundTasks`；抽取 + ingest 经线程卸载（如 `asyncio.to_thread` / 线程池），避免堵事件循环 |
| 6 | 状态机 | `pending` → `running` →（可选 `enriching`）→ `succeeded` / `succeeded_partial` / `failed` |
| 7 | 轮询 | 不新增 job API；前端依赖现有 `GET .../sources` 短轮询 |
| 8 | 重启恢复 | lifespan 扫描并重调度 `pending` / `running` / `enriching` |
| 9 | 队列 | **不上** Celery / Redis 等独立 worker |

---

## 3. 数据流

```text
POST .../sources/upload | upload-tree | upload-zip
  → 校验白名单
  → 写入原件（ZIP：解压到 KB 目录）
  → 每个目标文件预登记 Source：
       status=pending
       source_id = 最终 ingest 用的 .md/.txt 相对路径派生 id（与 LocalFileStore 一致）
       uri 指向原件或预期 sibling .md（实现可选；ingest 成功后以 md uri 为准）
  → 202 + SourceUploadResponse(
        accepted_async=true,
        files_total / results 含 source_id + relative_path,
        claims_* = 0, ingest_summary 可为空或「已接收」
      )
  → BackgroundTasks（每文件或批量）：
       pending → running
       若可抽取类型：materialize_markdown_for_ingest → sibling .md
       orchestrator.ingest(md/txt)
       成功后调度既有 enrich_source / enrich_chunks
       抽取或 ingest 失败 → status=failed（原因记入日志；列表可见 failed）
```

`.md` / `.txt`：无抽取步骤，直接 ingest。  
可抽取类型：原件保留；ingest 只读派生 `.md`。

---

## 4. 模块

| 模块 | 职责 |
|------|------|
| `admin_api/routes_sources.py` | 上传入口改为「落盘 + 预登记 + 调度」；返回 202 |
| `admin_api` 后台任务（可抽 `admin_api/upload_jobs.py`） | `running` → materialize → ingest → enrich；失败标 `failed` |
| `admin_api/schemas.py` | `SourceUploadResponse.accepted_async` |
| `app/main.py` lifespan | 恢复 `pending` / `running`（及现有 `enriching`） |
| `web` SourcesPage | 处理 202；提示「已接收，后台编译中」；短轮询至无 pending/running |
| `web` SourceFileBrowser | 确认 `pending`/`running`/`failed` 文案（已有基础标签） |

预登记须保证 **source_id 与后续 ingest 一致**，避免重复 Source 或列表闪断。

---

## 5. API 约定

- **成功接收**：HTTP `202`，`accepted_async=true`，`results` 列出已接受文件（`source_id`、`relative_path`/`directory`），计数类字段先为 0。
- **拒绝**：扩展名非法、路径不安全、写盘失败 → 4xx；**不**因后台 OCR/ingest 失败而让本次 HTTP 失败。
- **兼容**：旧客户端若忽略状态码仅看 JSON，仍可读 `results`；需知 claims 不会立即非零。
- **弃用行为**：上传接口不再在请求内等待 ingest 完成再 `200`。

---

## 6. 前端行为

1. 上传请求成功（202）→ 清空选择器 → 成功文案：「已接收 N 个文件，后台编译中」。
2. 立即 `loadSources()`，并启动短轮询（例如每 2s，最长 ~2–5 min 或直到无 `pending`/`running`）。
3. 列表项状态沿用 `compile_status`（映射自 `source.status`）；`failed` 显示「编译失败」。

---

## 7. 非目标

- 独立任务队列 / 多机 worker  
- 新的 `/uploads/{job_id}` 资源  
- 修改 Ask / Claim / 检索语义  
- 保证全部旧 `.doc` 可解析  

---

## 8. 测试

- API：上传 `.md` → `202` + `accepted_async`；短等后 `GET sources` 出现非 pending（或 mock 后台任务断言被调度）
- API：上传 docx/pdf fixture → 202；后台后存在 sibling `.md` 且 source 可达终态
- 校验失败（非法后缀）仍 400，无 Source 预登记
- 抽取失败（空文本 / 无 soffice 的 `.doc`）：HTTP 仍 202；随后 source `failed`
- 前端：202 后展示异步文案；轮询逻辑可单测或轻量组件测

---

## 9. 与文档上传 spec 的关系

`2026-09-15-akos-docs-pdf-upload-design.md` 的抽取与落盘规则不变；其中「请求内同步 ingest」由本 spec **取代**为后台执行。抽取失败从「上传 HTTP 400」改为「接受后 source=failed」（写盘前校验失败除外）。
