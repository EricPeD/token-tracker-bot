from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import ConfigDict  # Importar ConfigDict


class Settings(BaseSettings):
    telegram_token: str
    moralis_api_key: str
    etherscan_api_key: Optional[str] = None
    myst_contracts: list[str] = [
        "0x3c3e8eb3b432b6e4ab7b113f9c7f5bb8c2f993ce",  # Proxy actual
        "0x1379e8886a944d2d9d440b3d88df536aea08d9f3",  # viejo por si acaso
    ]
    poll_interval: int = 86400  # Segundos (1 vez cada 24h para producción)
    min_amount: float = 0.0  # Alertas > este valor
    sqlalchemy_echo: bool = False  # Controlar el echo de SQLAlchemy en producción
    debug_mode: bool = (
        False  # Nuevo atributo para controlar el modo de depuración de logging
    )

    model_config = ConfigDict(
        env_file=".env", case_sensitive=False
    )  # Usar ConfigDict directamente


settings = Settings()
