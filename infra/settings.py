"""AKOS 运行时配置。

默认值写在本文件。``.env`` 只覆盖环境相关项（库、LLM、鉴权等），前缀 ``AKOS_``。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用级配置；通过 ``request.app.state.settings`` 或 ``get_settings()`` 访问。"""

    model_config = SettingsConfigDict(
        env_prefix="AKOS_",
        env_file=str(_ENV_FILE),
        extra="ignore",
        populate_by_name=True,
    )

    # 存储 / 数据库
    data_root: str = "./data"
    database_url: str = "postgresql+psycopg://akos:akos@localhost:5432/akos"
    use_pg: bool = False

    # GraphPort：memory | postgres | neo4j
    graph_backend: str = "memory"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "akos-neo4j"

    default_domain_type: str = "ecommerce_cs"

    # LLM（OpenAI 兼容）；入库 / Ask / Wiki 默认依赖 Key，未配置会报错
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    # DeepSeek V4 默认开启 thinking；结构化抽取/合成建议关闭以提速并省 token
    llm_thinking: bool = False

    # LangSmith：支持 .env 中 LANGCHAIN_*（无 AKOS_ 前缀）或 AKOS_LANGSMITH_*
    langchain_tracing_v2: bool = Field(default=False, validation_alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", validation_alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="akos", validation_alias="LANGCHAIN_PROJECT")
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        validation_alias="LANGCHAIN_ENDPOINT",
    )
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "akos"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # 入库：规则 + LLM 混合抽 Claim（无单独开关；仅规则域见 RuleExtractor）
    chunk_max_chars: int = 3000
    chunk_max_per_doc: int = 40
    # auto=按标题密度选择；heading=按 H1/H2 切；general=段落/标题混合
    chunk_mode: str = "auto"
    # heading 模式下按此级别及更高层切分（更深标题留在块内）
    chunk_heading_level: int = 2
    extract_min_confidence: float = 0.5
    extract_open_predicates: bool = True
    # Claim 主体绑定产品：auto=有锚点时自动改写泛化主体；on=强制；off=关闭
    # 上传表单可覆盖。词表不可穷举，主要靠提示词示例 + 轻量后处理。
    subject_bind_mode: str = "auto"

    # Chunk：结构切分后 LLM 章节规划 + 元数据 enrich（关则仅结构块）
    chunk_llm: bool = True
    chunk_embedding: bool = False
    retrieval_top_k: int = 8
    # 图谱检索：动态预算 = min(top_k上限, 种子数 × 每种子条数)
    retrieval_graph_top_k: int = 20
    retrieval_graph_max_seeds: int = 7
    retrieval_graph_per_seed: int = 4
    # save_chunks 后硬删 stale 行（默认开）
    purge_stale_chunks: bool = True

    # Ask：LLM 综合回答 +（有会话时）问句 rewrite
    ask_synthesis: bool = True
    ask_synthesis_temperature: float = 0.2
    ask_synthesis_max_chunks: int = 5
    # 非 Claim（chunk/wiki）写入 LLM 时每条正文最大字符数
    ask_synthesis_content_max_chars: int = 800
    ask_synthesis_max_tokens: int = 1024

    # 三路检索权重（Claim / Wiki 主题页 / 原文 Chunk）
    retrieval_claim_weight: float = 1.0
    retrieval_wiki_weight: float = 0.9
    retrieval_chunk_weight: float = 0.8

    # Wiki：关则不入库后编译主题页；开则源文档 LLM 规划 + 主题页 LLM 合并
    wiki_compile: bool = True
    wiki_llm_cache: bool = True
    wiki_prompt_version: str = "v1"
    wiki_link_expand: bool = False
    wiki_split_min_chars: int = 5000
    wiki_migrate_flat: bool = True
    wiki_max_related: int = 12

    chunk_llm_segment_max_sections: int = 12
    chunk_min_tokens: int = 50
    chunk_min_score: float = 0.5
    embedding_enabled: bool = True
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    embedding_dims: int = 768
    embedding_device: str = "cpu"
    embedding_model_source: str = "modelscope"
    embedding_cache_dir: str = "./models"
    hf_endpoint: str = Field(default="", validation_alias="HF_ENDPOINT")
    rerank_enabled: bool = False
    rerank_provider: str = "bce"
    rerank_model: str = "maidalun/bce-reranker-base_v1"
    rerank_model_source: str = "modelscope"
    rerank_cache_dir: str = "./models"
    rerank_device: str = "cpu"
    rerank_max_length: int = 256
    rerank_top_n: int = 8
    rerank_min_score: float = 0.0

    # Topic cluster
    topic_cluster: bool = True
    topic_min_chunks: int = 1
    topic_graph_chunks: bool = True
    topic_llm_summary: bool = False
    topic_claim_boost: float = 0.1

    # 管理台原文预览
    source_content_max_bytes: int = 1_048_576

    @field_validator("llm_model", mode="before")
    @classmethod
    def _strip_llm_model(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
