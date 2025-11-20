from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    telegram_token: str
    moralis_api_key: str
    etherscan_api_key: Optional[str] = None
    wallet_address: Optional[str] = None  # Set via bot
    myst_contracts: list[str] = [
    "0x3c3e8eb3b432b6e4ab7b113f9c7f5bb8c2f993ce",  # Proxy actual
    "0x1379e8886a944d2d9d440b3d88df536aea08d9f3",  # viejo por si acaso
    ]
    poll_interval: int = 60  # Segundos
    min_amount: float = 0.0  # Alertas > este valor

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()