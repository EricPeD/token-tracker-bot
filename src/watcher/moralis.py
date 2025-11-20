# src/watcher/moralis.py
import aiohttp
from config.settings import settings
from typing import List, Dict, Any

MORALIS_BASE = "https://deep-index.moralis.io/api/v2.2"


async def get_myst_deposits(wallet_address: str) -> List[Dict[Any, Any]]:
    """
    Obtiene solo los depósitos entrantes de MYST (o cualquier token configurado)
    usando Moralis Wallet History API.
    """
    url = f"{MORALIS_BASE}/wallets/{wallet_address.lower()}/history"
    headers = {
        "X-API-Key": settings.moralis_api_key,
        "accept": "application/json"
    }
    params = {
        "chain": "polygon",
        "order": "DESC",
        "limit": 3  # Más histórico para evitar perder tx
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Moralis error {resp.status}: {text}")

            data = await resp.json()
            deposits = []

            for tx in data.get("result", []):
                for transfer in tx.get("erc20_transfers", []):
                    # Protección contra campos faltantes
                    to_addr = transfer.get("to_address", "").lower()
                    from_addr = transfer.get("from_address", "").lower()
                    token_addr = transfer.get("address", "").lower()

                    if not all([to_addr, token_addr]):
                        continue  # skip transferencias mal formadas

                    # Solo depósitos entrantes al wallet + solo MYST
                    if (to_addr == wallet_address.lower() and
                        token_addr in [c.lower() for c in settings.myst_contracts]):
                        
                        deposits.append({
                            "amount": transfer.get("value_formatted", "0"),
                            "amount_raw": transfer.get("value", "0"),
                            "from_address": from_addr,
                            "tx_hash": tx.get("hash", ""),
                            "block_timestamp": tx.get("block_timestamp", ""),
                            "token_symbol": transfer.get("token_symbol", "MYST"),
                        })

            return deposits