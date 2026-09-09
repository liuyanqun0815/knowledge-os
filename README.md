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
```

启用 PostgreSQL（`AKOS_USE_PG=true`）时，ingest 与 ask 可跨独立 CLI 进程共享持久化数据。

## API

```bash
uvicorn app.main:app --reload
```

启动后访问 `http://127.0.0.1:8000/docs` 查看 Swagger 文档。

## 管理台 Web UI

React 管理台位于 `web/`，经 Vite 代理调用 `/admin/*` 与 `POST /ask`。

**Implementation plan:** [`docs/superpowers/plans/2026-09-08-akos-admin-web.md`](docs/superpowers/plans/2026-09-08-akos-admin-web.md)

```bash
# 终端 A — 后端
uvicorn app.main:app --reload --port 8000

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
| `AKOS_LLM_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `AKOS_LLM_API_KEY` | LLM API Key（未配置时 corporate 库跳过 LLM 抽取） | 空 |
| `AKOS_LLM_MODEL` | LLM 模型名 | `gpt-4o-mini` |
| `ADMIN_API_TOKEN` | 管理 API 令牌（非空时 `/admin/*` 需 `X-Admin-Token`） | 空 |

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
