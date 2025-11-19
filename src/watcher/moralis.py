# src/watcher/moralis.py
import aiohttp
from config.settings import settings

MORALIS_BASE = "https://deep-index.moralis.io/api/v2.2"

async def get_myst_deposits(wallet_address: str): # con un comando /check llamas a esta función.
    url = f"{MORALIS_BASE}/wallets/history"
    headers = {"X-API-Key": settings.moralis_api_key, "accept": "application/json"}
    params = {
        "chain": "polygon",
        "wallet_addresses": wallet_address.lower(),
        "token_addresses": "0x1379e8886a944d2d9d440b3d88df536aea08d9f3",
        "order": "DESC",
        "limit": 20
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("result", [])
            else:
                text = await resp.text()
                raise Exception(f"Moralis error {resp.status}: {text}")