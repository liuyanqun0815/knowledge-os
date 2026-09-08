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

```bash
akos ingest samples/refund_policy_v3.md --type policy
akos ask "定制商品能否七天无理由退货？"
```

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

## PostgreSQL（可选）

单元测试默认使用 InMemory 适配器；启用 PG 需先启动 pgvector 并初始化 schema：

```bash
docker run -d --name akos-pg -e POSTGRES_PASSWORD=akos -e POSTGRES_USER=akos -e POSTGRES_DB=akos -p 5432:5432 pgvector/pgvector:pg16
psql postgresql://akos:akos@localhost:5432/akos -f infra/schema.sql
AKOS_USE_PG=true pytest tests/test_pg_knowledge.py -v
```
