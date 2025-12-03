import aiohttp
import json  # Importar json para JsonDecodeError
from src.config.settings import settings
from typing import List, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from aiohttp import ClientError, ClientResponseError
import asyncio
from src.config.logger_config import logger  # Importar el logger

MORALIS_BASE = "https://deep-index.moralis.io/api/v2.2"


# Decorador de reintentos para excepciones de cliente, timeout y errores 5x
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
async def get_wallet_deposits(
    wallet_address: str,
    token_addresses_to_monitor: List[str],
    client_session: aiohttp.ClientSession,
) -> List[Dict[Any, Any]]:
    """
    Obtiene todos los depósitos entrantes para tokens específicos en una wallet
    usando Moralis Wallet History API, implementando paginación y aplanando
    los datos de las transferencias ERC20.
    """
    url = f"{MORALIS_BASE}/wallets/{wallet_address.lower()}/history"
    headers = {"X-API-Key": settings.moralis_api_key, "accept": "application/json"}
    logger.debug(f"Moralis - get_wallet_deposits: Request URL: {url}")
    logger.debug(f"Moralis - get_wallet_deposits: Headers: {headers}")

    all_transactions = []
    cursor = None
    page_limit = (
        50  # Aumentar el límite de la página para obtener más transacciones por llamada
    )

    while True:
        params = {
            "chain": "polygon",
            "order": "DESC",
            "limit": page_limit,
        }
        if cursor:
            params["cursor"] = cursor
        logger.debug(f"Moralis - get_wallet_deposits: Request Params: {params}")

        async with client_session.get(
            url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            logger.debug(f"Moralis - get_wallet_deposits: Response Status: {resp.status}")
            if resp.status != 200:
                text = await resp.text()
                logger.error(
                    f"Moralis API error en get_wallet_deposits {resp.status}: {text}",
                    exc_info=True,
                )
                raise ClientResponseError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    message=f"Moralis API error: {text}",
                    headers=resp.headers,
                )
            try:
                data = await resp.json()
                logger.debug(
                    f"Moralis - get_wallet_deposits: Response Data: {json.dumps(data)}"
                )
            except json.JSONDecodeError as e:
                text = await resp.text()
                logger.error(
                    f"Error decodificando JSON de Moralis en get_wallet_deposits: {e}. Respuesta: {text}",
                    exc_info=True,
                )
                raise ClientError("Error de formato JSON de Moralis") from e

            all_transactions.extend(data.get("result", []))

            cursor = data.get("cursor")
            if not cursor:
                break  # No hay más páginas

    processed_deposits = []
    for tx in all_transactions:
        tx_hash = tx.get("hash")
        block_timestamp = tx.get("block_timestamp")
        # Consideramos solo ERC20_transfers para depósitos de tokens
        for erc20_transfer in tx.get("erc20_transfers", []):
            # Es un depósito si to_address coincide con nuestra wallet_address
            # y el token está en nuestra lista de monitorización
            if erc20_transfer.get(
                "to_address", ""
            ).lower() == wallet_address.lower() and erc20_transfer.get(
                "address", ""
            ).lower() in [
                addr.lower() for addr in token_addresses_to_monitor
            ]:
                processed_deposits.append(
                    {
                        "hash": tx_hash,
                        "token_address": erc20_transfer.get("address", ""),
                        "token_symbol": erc20_transfer.get("token_symbol", "UNKNOWN"),
                        "amount_raw": erc20_transfer.get("value", "0"),  # Raw amount
                        "amount": erc20_transfer.get(
                            "value_formatted", "0"
                        ),  # Formatted amount for display
                        "block_timestamp": block_timestamp,
                        "from_address": erc20_transfer.get("from_address", ""),
                    }
                )
    return processed_deposits


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(
        retry_if_exception_type(ClientResponseError)
        | retry_if_exception_type(ClientError)
        | retry_if_exception_type(asyncio.TimeoutError)
    ),
)
async def get_wallet_token_balances(
    wallet_address: str, client_session: aiohttp.ClientSession
) -> List[Dict[Any, Any]]:
    """
    Obtiene los balances de todos los tokens ERC20 para una wallet específica,
    usando el endpoint de Moralis Wallet API y manejando paginación.
    """
    url = f"{MORALIS_BASE}/wallets/{wallet_address.lower()}/tokens"
    headers = {"X-API-Key": settings.moralis_api_key, "accept": "application/json"}
    logger.debug(f"Moralis - get_wallet_token_balances: Request URL: {url}")
    logger.debug(f"Moralis - get_wallet_token_balances: Headers: {headers}")

    all_tokens = []
    cursor = None
    page_limit = 50  # Número de tokens por página

    while True:
        params = {
            "chain": "polygon",
            "limit": page_limit,
        }
        if cursor:
            params["cursor"] = cursor
        logger.debug(f"Moralis - get_wallet_token_balances: Request Params: {params}")

        async with client_session.get(
            url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            logger.debug(
                f"Moralis - get_wallet_token_balances: Response Status: {resp.status}"
            )
            if resp.status != 200:
                text = await resp.text()
                logger.error(
                    f"Moralis API error en get_wallet_token_balances {resp.status}: {text}",
                    exc_info=True,
                )
                raise ClientResponseError(
                    request_info=resp.request_info,
                    history=resp.history,
                    status=resp.status,
                    message=f"Moralis API error: {text}",
                    headers=resp.headers,
                )
            try:
                data = await resp.json()
                logger.debug(
                    f"Moralis - get_wallet_token_balances: Response Data: {json.dumps(data)}"
                )
            except json.JSONDecodeError as e:
                text = await resp.text()
                logger.error(
                    f"Error decodificando JSON de Moralis en get_wallet_token_balances: {e}. Respuesta: {text}",
                    exc_info=True,
                )
                raise ClientError("Error de formato JSON de Moralis") from e

            all_tokens.extend(data.get("result", []))

            cursor = data.get("cursor")
            if not cursor:
                break

    return all_tokens


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(
        retry_if_exception_type(ClientResponseError)
        | retry_if_exception_type(ClientError)
        | retry_if_exception_type(asyncio.TimeoutError)
    ),
)
async def get_wallet_net_worth(
    wallet_address: str, client_session: aiohttp.ClientSession
) -> str:
    """
    Obtiene el valor neto total en USD de una wallet.
    """
    url = f"{MORALIS_BASE}/wallets/{wallet_address.lower()}/net-worth"
    headers = {"X-API-Key": settings.moralis_api_key, "accept": "application/json"}
    params = {
        "chain": "polygon",
        "exclude_spam": "true",
    }
    logger.debug(f"Moralis - get_wallet_net_worth: Request URL: {url}")
    logger.debug(f"Moralis - get_wallet_net_worth: Request Params: {params}")

    async with client_session.get(
        url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=30)
    ) as resp:
        logger.debug(f"Moralis - get_wallet_net_worth: Response Status: {resp.status}")
        if resp.status != 200:
            text = await resp.text()
            logger.error(
                f"Moralis API error en get_wallet_net_worth {resp.status}: {text}",
                exc_info=True,
            )
            raise ClientResponseError(
                request_info=resp.request_info,
                history=resp.history,
                status=resp.status,
                message=f"Moralis API error: {text}",
                headers=resp.headers,
            )

        try:
            data = await resp.json()
            logger.debug(
                f"Moralis - get_wallet_net_worth: Response Data: {json.dumps(data)}"
            )  # Usar json.dumps
        except json.JSONDecodeError as e:
            text = await resp.text()
            logger.error(
                f"Error decodificando JSON de Moralis en get_wallet_net_worth: {e}. Respuesta: {text}",
                exc_info=True,
            )
            raise ClientError("Error de formato JSON de Moralis") from e

        return data.get("total_networth_usd", "0")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=(
        retry_if_exception_type(ClientResponseError)
        | retry_if_exception_type(ClientError)
        | retry_if_exception_type(asyncio.TimeoutError)
    ),
)
async def get_token_metadata(
    wallet_address: str, token_address: str, client_session: aiohttp.ClientSession
) -> Dict[str, Any] | None:
    """
    Obtiene los metadatos de un token ERC20 específico buscando
    dentro de los balances de la wallet.
    Este método es más fiable que el endpoint /erc20/{address}/metadata
    que a veces no encuentra tokens válidos.
    """
    logger.debug(
        f"Buscando metadatos para token {token_address} en la wallet {wallet_address}"
    )

    # Re-use the existing, reliable function
    all_balances = await get_wallet_token_balances(wallet_address, client_session)

    if not all_balances:
        logger.warning(
            f"No se obtuvieron balances para la wallet {wallet_address}, no se pueden encontrar metadatos."
        )
        return None

    # Find the specific token in the list
    for token_data in all_balances:
        if token_data.get("token_address", "").lower() == token_address.lower():
            logger.debug(
                f"Metadatos encontrados para {token_address} via balances: {token_data}"
            )
            return token_data

    logger.warning(
        f"No se encontraron metadatos para el token {token_address} en los balances de la wallet."
    )
    return None
