"""Download BCE reranker model from ModelScope (魔塔社区)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download BCE reranker from ModelScope")
    parser.add_argument(
        "--model",
        default="maidalun/bce-reranker-base_v1",
        help="ModelScope model id",
    )
    parser.add_argument(
        "--cache-dir",
        default="./models",
        help="Local cache directory",
    )
    args = parser.parse_args()

    from akos.adapters.retrieval.embedder import resolve_modelscope_model_dir
    from akos.adapters.retrieval.reranker import BceCrossEncoderReranker

    model_dir = resolve_modelscope_model_dir(args.model, args.cache_dir)
    print(f"ModelScope dir: {model_dir}")

    reranker = BceCrossEncoderReranker(model_dir, device="cpu")
    scores = reranker.score_pairs([("客服禁用语", "禁止使用：不知道、不归我管")])
    print(f"Smoke score={scores[0]:.4f}")
    print("Suggested .env:")
    print("AKOS_RERANK_ENABLED=true")
    print("AKOS_RERANK_PROVIDER=bce")
    print("AKOS_RERANK_MODEL_SOURCE=modelscope")
    print(f"AKOS_RERANK_MODEL={args.model}")
    print(f"AKOS_RERANK_CACHE_DIR={args.cache_dir}")
    print("AKOS_RERANK_DEVICE=cpu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
