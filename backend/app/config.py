"""Жүйенің баптаулары (.env файлынан немесе орта айнымалыларынан оқылады)."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # career-quest/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://careerquest:careerquest@localhost:5433/careerquest"
    data_dir: Path = ROOT / "data"
    reports_dir: Path = ROOT / "reports"
    cache_dir: Path = ROOT / "data" / "processed"

    # ҮТМ: auto — кілт болса OpenAI, болмаса офлайн режим
    llm_mode: str = "auto"  # auto | openai | offline
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_base_url: str | None = None
    llm_max_retries: int = 2  # JSON-схемаға сәйкес келмесе қайта сұрау саны

    embedding_model: str = "intfloat/multilingual-e5-small"   # толық ESCO индексі (pgvector)
    embedding_dim: int = 384
    offline_embedding_model: str = "BAAI/bge-m3"              # офлайн режимдегі каталог индексі
    offline_tau: float = 0.68                                 # офлайн τ (dev жиында бапталады)

    # Модель параметрлері (2.2-бөлім формулалары)
    top_k: int = 20          # ESCO үміткерлері саны
    tau: float = 0.86        # ұқсастық шегі τ (жергілікті dev жиында бапталады)
    alpha: float = 0.75      # гибридті балдағы α, (5) — Karrierewege validation жиынында таңдалған (Э4)
    smoothing_lambda: float = 1.0  # тегістеу λ, (4)
    weight_essential: float = 1.0
    weight_optional: float = 0.5

    jwt_secret: str = "career-quest-dev-secret-change-me-in-production-2026"
    jwt_ttl_minutes: int = 720
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def llm_enabled(self) -> bool:
        if self.llm_mode == "offline":
            return False
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
