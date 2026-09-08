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
