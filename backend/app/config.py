from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./kalshi.db"
    kalshi_api_base: str = "https://api.elections.kalshi.com/trade-api/v2"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    ingestion_interval_seconds: int = 60
    ingestion_market_limit: int = 50
    cors_origins: list[str] = ["http://localhost:3000"]
    paper_trading_starting_balance: float = 100.0


settings = Settings()
