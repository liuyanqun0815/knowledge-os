from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AKOS_", env_file=".env", extra="ignore")

    data_root: str = "./data"
    database_url: str = "postgresql+psycopg://akos:akos@localhost:5432/akos"
    use_pg: bool = False
    default_domain_type: str = "ecommerce_cs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
