"""Download embedding model from ModelScope (魔塔社区)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Download BGE model from ModelScope")
    parser.add_argument(
        "--model",
        default="AI-ModelScope/bge-base-zh-v1.5",
        help="ModelScope model id",
    )
    parser.add_argument(
        "--cache-dir",
        default="./models",
        help="Local cache directory",
    )
    args = parser.parse_args()

    from akos.adapters.retrieval.embedder import resolve_modelscope_model_dir, SentenceTransformerEmbedder

    model_dir = resolve_modelscope_model_dir(args.model, args.cache_dir)
    print(f"ModelScope dir: {model_dir}")

    embedder = SentenceTransformerEmbedder(model_dir, device="cpu")
    print(f"Loaded dims={embedder.dims}")
    print("Suggested .env:")
    print("AKOS_EMBEDDING_PROVIDER=local")
    print("AKOS_EMBEDDING_MODEL_SOURCE=modelscope")
    print(f"AKOS_EMBEDDING_MODEL={args.model}")
    print(f"AKOS_EMBEDDING_CACHE_DIR={args.cache_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
