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
    paper_trading_starting_balance: float = 1000.0
    exit_monitor_interval_seconds: int = 45
    exit_min_confidence_to_auto_execute: int = 70
    exit_max_auto_sell_amount: float = 100.0
    exit_max_data_staleness_seconds: int = 120
    exit_auto_max_sells_per_cycle: int = 3


settings = Settings()
