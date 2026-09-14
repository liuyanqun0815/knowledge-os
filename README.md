# AKOS — Agent-Native Knowledge Operating System

电商客服知识操作系统（模块化单体架构）。

## 安装

```bash
pip install -e ".[dev]"
```

## 测试

```bash
pytest
```

## CLI

所有命令必须指定知识库 `--kb`（`knowledge_base_id`）：

```bash
akos ingest samples/refund_policy_v3.md --kb <knowledge_base_id> --type policy
akos ask "定制商品能否七天无理由退货？" --kb <knowledge_base_id>
akos inspect <claim_id> --kb <knowledge_base_id>
akos lint --kb <knowledge_base_id>
akos lint --kb <knowledge_base_id> --format json
akos wiki-export --kb <knowledge_base_id> --out ./wiki-out
```

启用 PostgreSQL（`AKOS_USE_PG=true`）时，ingest 与 ask 可跨独立 CLI 进程共享持久化数据。

## 知识库 Lint / Wiki 导出

借鉴 [LLM Wiki](https://github.com/luotwo/llm-wiki) 的 **Lint（健康检查）** 与 **Wiki 视图层（只读导出）**；PG Claim 仍为唯一权威，导出的 Markdown 不回写入库。

| 能力 | CLI | Admin API |
|------|-----|-----------|
| Lint | `akos lint --kb <id>` | `GET /admin/knowledge-bases/{kb_id}/lint` |
| Wiki 导出 | `akos wiki-export --kb <id> [--out dir]` | `POST /admin/knowledge-bases/{kb_id}/wiki/export` |
| Wiki 编译层 | （enrich 后自动，需 `AKOS_WIKI_COMPILE`） | `POST /admin/knowledge-bases/{kb_id}/wiki/compile`（可选 `?source_id=`） |
| 清理 stale chunks | （`save_chunks` 后自动，需 `AKOS_PURGE_STALE_CHUNKS`） | `POST /admin/knowledge-bases/{kb_id}/chunks/purge-stale` |
| 主题簇重建 | （enrich / wiki 导出前自动） | `POST /admin/knowledge-bases/{kb_id}/topics/rebuild` |

Lint 检查项：`conflict`（同 family 多条 active）、`missing_evidence`、`orphan_source`、`quarantine_backlog`。

Wiki 导出目录结构（Obsidian 友好）：

```
{output}/
  index.md              # 文档、主题与实体索引
  log.md                # 导出时间戳
  topic-{name}.md       # 主题簇页（Claims / 章节 / 相关）
  source-{id}.md        # 文档页 + 关联 Claim
  {subject}.md          # 实体页 + [[wikilink]]
```

`AKOS_TOPIC_CLUSTER=true` 时，Wiki 的 `index.md` 含 `## 主题` 区；手动重建：`POST /admin/knowledge-bases/{kb_id}/topics/rebuild`（返回 `topics_created` / `topics_updated` / `topics_stale` / `edges`）。

默认导出路径：`{AKOS_DATA_ROOT}/{kb_id}/wiki/`（只读导出视图，不回写）。

**编译层（Ask 三路检索用）**路径：`{AKOS_DATA_ROOT}/kb/{kb_id}/wiki/`（`topic-*.md` + `.meta/pages.json`）。由 `AKOS_WIKI_COMPILE` 在 enrich 后增量更新，或手动 `POST .../wiki/compile`；模板/LLM 由 `AKOS_WIKI_COMPILE_LLM` 控制。与导出路径不同，勿混用。

上传完成后 API 响应含 `ingest_summary`（规则生成，无 LLM）。

**Implementation plan:** [`docs/superpowers/plans/2026-09-09-akos-wiki-lint-export.md`](docs/superpowers/plans/2026-09-09-akos-wiki-lint-export.md) · Compiled wiki [`2026-09-14-akos-compiled-wiki-retrieval.md`](docs/superpowers/plans/2026-09-14-akos-compiled-wiki-retrieval.md)

```bash
pytest -v tests/test_knowledge_lint.py tests/test_wiki_export.py \
  tests/test_admin_lint_api.py tests/test_admin_wiki_export_api.py \
  tests/test_upload_ingest_summary.py
```

与 LLM Wiki 对照：

| LLM Wiki | AKOS 本计划 |
|----------|-------------|
| Lint 口头指令 | `akos lint` + Admin API |
| wiki/ 目录 | `wiki-export` 从 Claim 生成 |
| Ingest 更新已有页 | 上传 `ingest_summary`（规则摘要 v1） |
| Query 回写 | 暂未实现 |

## API

```bash
# 推荐 factory 模式：reload 时重建 app，避免旧代码残留（如 ZIP 上传不生效）
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

启动后访问 `http://127.0.0.1:8000/docs` 查看 Swagger 文档。

## 管理台 Web UI

React 管理台位于 `web/`，经 Vite 代理调用 `/admin/*` 与 `POST /ask`。覆盖 F0–F4：知识库与文档管理、Claim 浏览、隔离审批、AnswerV2 问答（含 `as_of` / 轨迹）及文档演化上传。

**Implementation plan:** [`docs/superpowers/plans/2026-09-08-akos-admin-web.md`](docs/superpowers/plans/2026-09-08-akos-admin-web.md) · F4+ [`2026-09-09-akos-admin-web-f4-plus.md`](docs/superpowers/plans/2026-09-09-akos-admin-web-f4-plus.md)

```bash
# 终端 A — 后端
uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

# 终端 B — 前端
cd web && npm install && npm run dev
```

浏览器打开 [http://127.0.0.1:5173](http://127.0.0.1:5173)。详细说明与手工 E2E 验收清单见 [`web/README.md`](web/README.md)。

可选鉴权：后端 `.env` 设置 `ADMIN_API_TOKEN`，前端 `web/.env.local` 设置 `VITE_ADMIN_API_TOKEN`（值需一致）。

## 环境变量

复制 `.env.example` 为 `.env` 并按需修改：

```bash
cp .env.example .env
```

| 变量 | 说明 | 默认 |
|------|------|------|
| `AKOS_DATA_ROOT` | 本地文件存储根目录 | `./data` |
| `AKOS_DATABASE_URL` | PostgreSQL 连接串 | `postgresql+psycopg://akos:akos@localhost:5432/akos` |
| `AKOS_USE_PG` | 启用 PostgreSQL 适配器 | `false` |
| `AKOS_GRAPH_BACKEND` | 图存储后端 | `memory`（`.env.example` 为 `postgres`） |
| `AKOS_NEO4J_URI` / `USER` / `PASSWORD` | Neo4j 连接（`graph_backend=neo4j` 时） | 见 `.env.example` |
| `AKOS_FILES_BACKEND` | 文件存储后端（规划） | `local` |
| `AKOS_DEFAULT_DOMAIN_TYPE` | 新建知识库默认领域 | `ecommerce_cs` |
| `AKOS_LLM_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `AKOS_LLM_API_KEY` | LLM API Key（未配置时跳过 LLM 补抽） | 空 |
| `AKOS_LLM_MODEL` | LLM 模型名 | `gpt-4o-mini` |
| `AKOS_EXTRACT_RULES` | 启用规则抽取（同步阶段） | `true` |
| `AKOS_EXTRACT_LLM` | 启用 LLM 后台补抽 | `true` |
| `AKOS_CHUNK_MAX_CHARS` | 单切片最大字符数 | `3000` |
| `AKOS_CHUNK_MAX_PER_DOC` | 单文档最大切片数 | `40` |
| `AKOS_EXTRACT_MIN_CONFIDENCE` | LLM Claim 最低置信度 | `0.5` |
| `AKOS_EXTRACT_OPEN_PREDICATES` | 开放谓词（true=LLM 可自创谓词并懒注册；false=名单外进 quarantine） | `true` |
| `AKOS_PURGE_STALE_CHUNKS` | save_chunks 后硬删 stale 行 | `true` |
| `AKOS_WIKI_COMPILE` | 同库编译层增量更新（false 时 Ask 仍为双路） | `true` |
| `AKOS_WIKI_COMPILE_LLM` | 主题页 LLM 合并（false 则确定性模板） | `true` |
| `AKOS_RETRIEVAL_CLAIM_WEIGHT` | 三路融合 Claim 权重 | `1.0` |
| `AKOS_RETRIEVAL_WIKI_WEIGHT` | 三路融合 Wiki 主题页权重 | `0.9` |
| `AKOS_RETRIEVAL_CHUNK_WEIGHT` | 三路融合原文 Chunk 权重 | `0.8` |
| `AKOS_WIKI_LINK_EXPAND` | 沿 `[[wikilink]]` 扩展检索（一期默认关） | `false` |
| `AKOS_WIKI_HIERARCHY` | 启用 Wiki 目录层级（hub/leaf/snippet）；false 保持平铺 `topic-` | `true` |
| `AKOS_WIKI_HIERARCHY_LLM` | LLM 辅助选父主题（一期默认关） | `false` |
| `AKOS_WIKI_MIGRATE_FLAT` | 编译时清理根目录旧 `topic-*.md` | `true` |
| `AKOS_WIKI_MAX_RELATED` | 相关主题上限（同 hub 优先） | `12` |
| `AKOS_TOPIC_CLUSTER` | 启用主题簇（PG/图/Wiki topic 页） | `true` |
| `AKOS_TOPIC_MIN_CHUNKS` | 主题簇最少 chunk 数（仅 claim 命中时仍可成簇） | `1` |
| `AKOS_TOPIC_GRAPH_CHUNKS` | 图同步时写入 Chunk 节点与「包含段落」边 | `true` |
| `AKOS_TOPIC_LLM_SUMMARY` | 主题摘要 LLM（一期默认关） | `false` |
| `AKOS_TOPIC_CLAIM_BOOST` | 同簇 claim 检索加权 α（一期未接线，预留） | `0.1` |
| `ADMIN_API_TOKEN` | 管理 API 令牌（非空时 `/admin/*` 需 `X-Admin-Token`） | 空 |

## Hybrid LLM 抽取（两段式）

上传文档采用 **规则同步 + LLM 异步补抽**：

1. **同步（秒级）**：`POST /admin/.../sources/upload` 仅跑规则抽取 → 立刻可问答；若 `AKOS_EXTRACT_LLM=true` 且已配置 Key，source 状态为 `enriching`。
2. **后台**：FastAPI `BackgroundTasks` 调用 `EnrichmentRunner` 切片 + `DomainLlmExtractor` 补抽 → 去重合并 → 白名单外谓词进 quarantine → 终态 `succeeded` / `succeeded_partial`。

**Implementation plan:** [`docs/superpowers/plans/2026-09-09-akos-hybrid-llm-extraction.md`](docs/superpowers/plans/2026-09-09-akos-hybrid-llm-extraction.md)

| 开关 | 行为 |
|------|------|
| `AKOS_EXTRACT_LLM=false` | 仅规则抽取，与一期行为一致 |
| 无 `AKOS_LLM_API_KEY` | 自动跳过补抽（即使 `AKOS_EXTRACT_LLM=true`） |
| 超出切片上限 | `succeeded_partial`，规则 Claim 仍可用 |

```bash
# Hybrid 单元 / 集成
pytest -v tests/test_chunker.py tests/test_domain_llm_extractor.py \
  tests/test_enrichment_runner.py tests/test_hybrid_extraction_api.py \
  tests/test_compiler_apply_extracted.py

# 规则-only 回归（InMemory，避免 PG 依赖）
$env:AKOS_USE_PG='false'; $env:AKOS_EXTRACT_LLM='false'
pytest -v tests/test_e2e_sample.py tests/test_admin_kb_api.py --tb=short
```

## Phase 2.4 验收

Phase 2.4 聚焦生产部署与运营：Docker Compose（PG + Neo4j + MinIO + API）、Procedural Memory、admin 完善（claims/quarantine/debug）。

```bash
# 全量单元测试（默认 InMemory，排除 web）
pytest -v --ignore=web

# Phase 2.4 §8.4 E2E 验收（procedure / quarantine / debug / docker 配置）
pytest -v tests/test_phase24_e2e.py

# admin API 细分（claims / quarantine / debug graph）
pytest -v tests/test_admin_phase24.py

# Procedural Memory 单元
pytest -v tests/test_procedure_memory.py
```

**Docker Compose 启动（生产栈）：**

```bash
cd deploy
cp .env.production.example .env.production
# 按需编辑 AKOS_LLM_API_KEY、ADMIN_API_TOKEN 等

docker compose up --build

# 开发 overlay（暴露端口 + 源码热重载）
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

首次启动 PostgreSQL 后，从宿主机初始化 schema：

```bash
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/schema.sql
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/migrations/002_knowledge_bases.sql
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/migrations/003_evolution.sql
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/migrations/004_procedures.sql
```

验收清单（spec §8.4）：

- `docker compose up` 可启动 PG + Neo4j + MinIO + API（`deploy/docker-compose.yml`、`Dockerfile` 就绪）
- 后台创建知识库 → 上传 → compile → ask（指定 `knowledge_base_id`）全链路
- Neo4j Browser 可见该库实体/关系（节点/关系带 `kb_id`）
- `akos ask --kb <id> "仅退款流程怎么走？"` → `procedure_id` + 流程 steps（`test_procedure_ask_returns_steps`）
- quarantine 人工 approve 后进入主图（`test_quarantine_approve_creates_active_claim`）
- `POST /admin/knowledge-bases/{kb_id}/debug/ask` 返回含 `retrieve`、`verify` 的 trace

## Phase 2.3 验收

Phase 2.3 聚焦可信问答：Verification Agent span 校验、竞争 Claim 冲突检测、AnswerV2 字段与 LangGraph trace 调试。

```bash
# 全量单元测试（默认 InMemory，排除 web）
pytest -v --ignore=web

# verification 核心规则（span 匹配 / 冲突 / confidence）
pytest -v tests/test_verification_service.py

# ask 流水线 verify 节点
pytest -v tests/test_verify_ask.py

# ingest verify_sample 高风险谓词 quarantine
pytest -v tests/test_ingest_verify_sample.py

# LangGraph trace + POST /ask AnswerV2 字段
pytest -v tests/test_ask_trace.py

# Phase 2.3 §7.5 E2E 验收（unverified / conflict / trace）
pytest -v tests/test_verification_e2e.py
```

验收清单（spec §7.5）：

- 手工注入 span 与原文不符的 Claim → `ask` 返回 `verification_status=unverified`，或 ingest `verify_sample` 将高风险 Claim quarantine
- 同 family 两条 active Claim → `verification_status=conflict` 且 `competing_claim_ids` 列出竞争 Claim
- `POST /ask?include_trace=true` 返回 trace JSON，含 `retrieve`、`verify` 等节点名

## Phase 2.2 验收

Phase 2.2 聚焦知识演化：政策 V2 替换 V1 时自动 Diff → supersede；问答支持 `as_of` 时序查询与 Claim 版本历史。

```bash
# 全量单元测试（默认 InMemory）
pytest -v

# Phase 2.2 evolution 模块（differ / applier / as_of）
pytest -v tests/test_evolution_differ.py tests/test_evolution_applier.py

# ingest 演化流水线（v3 → v4 supersede）
pytest -v tests/test_evolve_ingest.py

# as_of 时序问答 + parse_time
pytest -v tests/test_as_of_query.py

# evolution API（upload replaces、evolve、claim history）
pytest -v tests/test_evolution_api.py

# Phase 2.2 §6.5 E2E 验收（v3→v4 / as_of / history）
pytest -v tests/test_evolution_e2e.py

# PostgreSQL 演化持久化（需 PG）
AKOS_USE_PG=true pytest -v tests/test_evolution_e2e.py tests/test_evolve_ingest.py
```

验收清单（spec §6.5）：

- `refund_policy_v3.md` → `refund_policy_v4.md`（运费承担方 买家→平台）自动 supersede
- Diff 报告 1 条 supersede；active claim 为新值「平台」
- `as_of(v3 生效日)` 仍返回「买家」（orchestrator 与 `POST /ask`）
- `GET /claims/{family_id}/history` 与 admin history 返回 2 版本时间线

## Phase 2.1 验收

Phase 2.1 聚焦知识库隔离、DomainPort 与 admin 上传；LLM 抽取为 stub（无 Key 时 corporate 库跳过抽取）。

```bash
# 全量单元测试（默认 InMemory）
pytest -v

# 一期 e2e：种子库 test-ecommerce（PG）或 default（InMemory）
pytest -v tests/test_e2e_sample.py

# 知识库隔离 + corporate 领域骨架
pytest -v tests/test_kb_isolation.py tests/test_corporate_domain_skeleton.py

# PostgreSQL 持久化（需先启动 pgvector 并执行 schema）
docker run -d --name akos-pg -e POSTGRES_PASSWORD=akos -e POSTGRES_USER=akos -e POSTGRES_DB=akos -p 5432:5432 pgvector/pgvector:pg16
psql postgresql://akos:akos@localhost:5432/akos -f infra/schema.sql
psql postgresql://akos:akos@localhost:5432/akos -f infra/migrations/002_knowledge_bases.sql
AKOS_USE_PG=true pytest -v tests/test_pg_knowledge.py tests/test_cli_kb_persistence.py tests/test_admin_kb_api.py tests/test_e2e_sample.py

# 可选：配置 AKOS_LLM_API_KEY 后运行 LLM 集成测试
AKOS_LLM_API_KEY=sk-... pytest -v tests/test_corporate_domain_skeleton.py -k llm_integration
```

验收清单（spec §5.5）：

- admin 创建 `corporate_culture` 库并上传文档（无 LLM Key 时 claims 可能为 0；有 Key 时 claims > 0）
- 两个知识库 Claim 互不可见（`test_kb_isolation`）
- `POST /ask` 带 `knowledge_base_id` 只命中该库
- `akos ask --kb <id>` 跨 CLI 进程可答（PG）
- 一期 e2e 在 `test-ecommerce` 库 PASS（`tests/test_e2e_sample.py`）

## PostgreSQL（可选）

单元测试默认使用 InMemory 适配器；启用 PG 需先启动 pgvector 并初始化 schema：

```bash
docker run -d --name akos-pg -e POSTGRES_PASSWORD=akos -e POSTGRES_USER=akos -e POSTGRES_DB=akos -p 5432:5432 pgvector/pgvector:pg16
psql postgresql://akos:akos@localhost:5432/akos -f infra/schema.sql
AKOS_USE_PG=true pytest tests/test_pg_knowledge.py -v
```
