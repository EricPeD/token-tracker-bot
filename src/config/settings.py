from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    telegram_token: str
    etherscan_api_key: str
    moralis_api_key: str
    wallet_address: Optional[str] = None  # Set via bot
    myst_contract: str = "0x1379E8886A944d2D9d440b3d88DF536Aea08d9F3"
    poll_interval: int = 60  # Segundos
    min_amount: float = 0.0  # Alertas > este valor

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()