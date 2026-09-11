"""AKOS 运行时配置。

从环境变量加载，前缀 ``AKOS_``，可选读取项目根 ``.env``。
字段说明与分组见 ``.env.example`` 与 README「环境变量」。
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

    # LLM（OpenAI 兼容）；llm_api_key 为空时 enrich 流程自动跳过
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

    # Hybrid 抽取
    extract_rules: bool = True
    extract_llm: bool = True
    chunk_max_chars: int = 3000
    chunk_max_per_doc: int = 40
    extract_min_confidence: float = 0.5
    extract_open_predicates: bool = True

    # Chunk 索引
    chunk_index: bool = True
    chunk_llm_enrich: bool = True
    chunk_embedding: bool = False
    retrieval_top_k: int = 8

    # Ask synthesis
    ask_synthesis: bool = True
    ask_synthesis_temperature: float = 0.2
    ask_synthesis_max_chunks: int = 5
    ask_synthesis_max_tokens: int = 1024

    # Wiki LLM
    wiki_llm: bool = False
    wiki_llm_cache: bool = True
    wiki_prompt_version: str = "v1"

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
