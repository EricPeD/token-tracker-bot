import aiohttp
from src.config.settings import settings
from typing import List, Dict, Any
import sys
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from aiohttp import ClientError, ClientResponseError
import asyncio

MORALIS_BASE = "https://deep-index.moralis.io/api/v2.2"


# Decorador de reintentos para excepciones de cliente, timeout y errores 5xx
@retry(
    stop=stop_after_attempt(3),  # Intentar 3 veces
    wait=wait_exponential(
        multiplier=1, min=4, max=10
    ),  # Espera exponencial entre 4 y 10 segundos
    retry=(
        retry_if_exception_type(ClientResponseError)
        | retry_if_exception_type(ClientError)
        | retry_if_exception_type(asyncio.TimeoutError)
    ),
)
async def get_myst_deposits(
    wallet_address: str, token_addresses_to_monitor: List[str]
) -> List[Dict[Any, Any]]:
    """
    Obtiene todos los depósitos entrantes de MYST (o cualquier token configurado)
    usando Moralis Wallet History API, implementando paginación.
    """
    url = f"{MORALIS_BASE}/wallets/{wallet_address.lower()}/history"
    headers = {"X-API-Key": settings.moralis_api_key, "accept": "application/json"}

    all_transfers = []
    cursor = None
    page_limit = 20  # Número de transacciones por página

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30)
    ) as session:  # Añadir timeout
        while True:
            params = {
                "chain": "polygon",
                "order": "DESC",
                "limit": page_limit,
            }
            if cursor:
                params["cursor"] = cursor

            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    # En lugar de una Exception genérica, lanzar ClientResponseError para que tenacity la detecte
                    text = await resp.text()
                    print(
                        f"ERROR Moralis API response {resp.status}: {text}",
                        file=sys.stderr,
                    )
                    # Propagar el error para que tenacity pueda intentar reintentar
                    raise ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=f"Moralis API error: {text}",
                        headers=resp.headers,
                    )

                data = await resp.json()
                all_transfers.extend(data.get("result", []))

                cursor = data.get("cursor")
                if not cursor:
                    break  # No hay más páginas

        deposits = []
        for tx in all_transfers:
            for transfer in tx.get("erc20_transfers", []):
                # Protección contra campos faltantes
                to_addr = transfer.get("to_address", "").lower()
                from_addr = transfer.get("from_address", "").lower()
                token_addr = transfer.get("address", "").lower()

                if not all([to_addr, token_addr]):
                    continue  # skip transferencias mal formadas

                # Solo depósitos entrantes al wallet + solo MYST
                if to_addr == wallet_address.lower() and token_addr in [
                    c.lower() for c in token_addresses_to_monitor
                ]:
                    deposits.append(
                        {
                            "amount": transfer.get("value_formatted", "0"),
                            "amount_raw": transfer.get("value", "0"),
                            "from_address": from_addr,
                            "tx_hash": tx.get("hash", ""),
                            "block_timestamp": tx.get("block_timestamp", ""),
                            "token_symbol": transfer.get("token_symbol", "MYST"),
                        }
                    )

        return deposits
