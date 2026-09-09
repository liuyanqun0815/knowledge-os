# Phase 2.4 Task 2 Report — Docker Compose production stack

**Baseline:** Phase 2.4 Task 1 pending (Neo4j GraphPort adapter)

**Commit:** `feat: add docker-compose production stack`

## Summary

Added production Docker deployment per spec §8.1: `Dockerfile` for `akos-api`, base `deploy/docker-compose.yml` (PG + Neo4j + MinIO + optional Redis + API), dev overlay with port exposure and hot-reload source mount, and production env template.

## Files created

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.11 slim; `pip install -e ".[dev,neo4j]"`; uvicorn on :8000 |
| `deploy/docker-compose.yml` | postgres, neo4j, minio, redis (profile), akos-api |
| `deploy/docker-compose.dev.yml` | Expose DB/Neo4j/MinIO/Redis ports; mount source + `--reload` |
| `deploy/.env.production.example` | All `AKOS_*` production vars + `ADMIN_API_TOKEN` |
| `.dockerignore` | Exclude git, venv, web/node_modules, local data |

## Files modified

| File | Change |
|------|--------|
| `.env.example` | Added `AKOS_GRAPH_BACKEND`, `AKOS_NEO4J_*`, `AKOS_FILES_BACKEND` comments |
| `pyproject.toml` | Added optional `[neo4j]` extra (required by Dockerfile install) |

## Services (docker-compose.yml)

| Service | Image | Notes |
|---------|-------|-------|
| `postgres` | `pgvector/pgvector:pg16` | Healthcheck; user/db `akos` |
| `neo4j` | `neo4j:5` | `NEO4J_AUTH=neo4j/akos-neo4j` |
| `minio` | `minio/minio` | Console on :9001 |
| `redis` | `redis:7` | Optional `--profile redis` |
| `akos-api` | build `..` | Depends on postgres + neo4j + minio |

## Usage

```bash
cd deploy
cp .env.production.example .env.production
# Edit AKOS_LLM_API_KEY, ADMIN_API_TOKEN, etc.

# Production stack
docker compose up --build

# Dev overlay (expose ports + hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# With Redis hot memory
docker compose -f docker-compose.yml -f docker-compose.dev.yml --profile redis up --build
```

**Schema init:** After first `postgres` start, apply migrations from host:

```bash
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/schema.sql
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/migrations/002_knowledge_bases.sql
psql postgresql://akos:akos@localhost:5432/akos -f ../infra/migrations/003_evolution.sql
```

(Use `localhost:5432` only when dev overlay exposes the port.)

## Environment mapping (spec §8.1)

| Variable | Production value | Port |
|----------|------------------|------|
| `AKOS_GRAPH_BACKEND` | `neo4j` | GraphPort |
| `AKOS_BM25_BACKEND` | `postgres` | RetrievalPort |
| `AKOS_FILES_BACKEND` | `minio` | FilePort |
| `AKOS_MEMORY_HOT` | `pg` (or `redis` with profile) | MemoryPort |

## Verification

- CI does **not** run `docker compose` (per task scope).
- Existing pytest suite unchanged: `pytest -v --ignore=web` (82 passed baseline).

## Next

- Task 1: Wire `AKOS_GRAPH_BACKEND` in `infra/settings.py` + Neo4j GraphPort adapter
- Task 6: README Phase 2.4 docker acceptance section
