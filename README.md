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

## Phase 2.1 验收

Phase 2.1 聚焦知识库隔离、DomainPort 与 admin 上传；LLM 抽取为 stub（无 Key 时 corporate 库跳过抽取）。

```bash
# 全量单元测试（默认 InMemory）
pytest -v

# 知识库隔离 + corporate 领域骨架
pytest -v tests/test_kb_isolation.py tests/test_corporate_domain_skeleton.py

# PostgreSQL 持久化（需先启动 pgvector 并执行 schema）
docker run -d --name akos-pg -e POSTGRES_PASSWORD=akos -e POSTGRES_USER=akos -e POSTGRES_DB=akos -p 5432:5432 pgvector/pgvector:pg16
psql postgresql://akos:akos@localhost:5432/akos -f infra/schema.sql
psql postgresql://akos:akos@localhost:5432/akos -f infra/migrations/002_knowledge_bases.sql
AKOS_USE_PG=true pytest -v tests/test_pg_knowledge.py tests/test_cli_kb_persistence.py tests/test_admin_kb_api.py

# 可选：配置 AKOS_LLM_API_KEY 后运行 LLM 集成测试
AKOS_LLM_API_KEY=sk-... pytest -v tests/test_corporate_domain_skeleton.py -k llm_integration
```

验收清单（spec §5.5）：

- admin 创建 `corporate_culture` 库并上传文档（无 LLM Key 时 claims 可能为 0；有 Key 时 claims > 0）
- 两个知识库 Claim 互不可见（`test_kb_isolation`）
- `POST /ask` 带 `knowledge_base_id` 只命中该库
- `akos ask --kb <id>` 跨 CLI 进程可答（PG）
- 一期 e2e 在 `test-ecommerce` 库 PASS

## PostgreSQL（可选）

单元测试默认使用 InMemory 适配器；启用 PG 需先启动 pgvector 并初始化 schema：

```bash
docker run -d --name akos-pg -e POSTGRES_PASSWORD=akos -e POSTGRES_USER=akos -e POSTGRES_DB=akos -p 5432:5432 pgvector/pgvector:pg16
psql postgresql://akos:akos@localhost:5432/akos -f infra/schema.sql
AKOS_USE_PG=true pytest tests/test_pg_knowledge.py -v
```
