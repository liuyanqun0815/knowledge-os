from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKOS_", env_file=".env", extra="ignore")

    data_root: str = "./data"
    database_url: str = "postgresql+psycopg://akos:akos@localhost:5432/akos"
    use_pg: bool = False
    graph_backend: str = "memory"  # memory | postgres | neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "akos-neo4j"
    default_domain_type: str = "ecommerce_cs"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    extract_rules: bool = True
    extract_llm: bool = True
    chunk_max_chars: int = 3000
    chunk_max_per_doc: int = 40
    extract_min_confidence: float = 0.5
    extract_open_predicates: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
