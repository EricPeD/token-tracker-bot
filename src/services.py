# src/services.py
import aiohttp
from typing import List, Dict, Any
from sqlalchemy import select
from src.models import (
    AsyncSessionLocal,
    User,
    UserToken,
    Transaction,
    LastTx,
)
from src.watcher.moralis import get_wallet_deposits
from src.config.logger_config import logger


async def check_and_process_deposits(
    user_id: int, client_session: aiohttp.ClientSession
) -> List[Dict[Any, Any]]:
    """
    Unifica la lógica para comprobar y procesar nuevos depósitos para un usuario.
    1. Obtiene los datos del usuario y los tokens a monitorizar.
    2. Llama a la API de Moralis para obtener el historial de transacciones.
    3. Compara con la BD para encontrar depósitos nuevos.
    4. Guarda los nuevos depósitos y actualiza el último timestamp.
    5. Devuelve los nuevos depósitos encontrados.
    """
    truly_new_deposits = []
    try:
        # === BLOCK 1: Read data for API call in a separate session ===
        wallet_address = ""
        token_addresses_to_monitor = []
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user or not user.wallet_address:
                logger.warning(
                    f"Usuario {user_id} no encontrado o sin wallet, saltando."
                )
                return []
            wallet_address = user.wallet_address

            tokens_result = await session.execute(
                select(UserToken.token_address).where(UserToken.user_id == user_id)
            )
            token_addresses_to_monitor = list(tokens_result.scalars())

        if not token_addresses_to_monitor:
            logger.info(f"Usuario {user_id} no monitoriza ningún token. Saltando.")
            return []

        # === EXTERNAL API CALL ===
        deposits = await get_wallet_deposits(
            wallet_address, token_addresses_to_monitor, client_session
        )
        if not deposits:
            return []

        # === BLOCK 2: Read/Write operations in a single, clean transaction ===
        async with AsyncSessionLocal() as session:
            async with session.begin():  # Start a single transaction
                # 1. Load last known timestamp
                last_tx_obj = await session.get(LastTx, user_id)
                last_known_timestamp = (
                    last_tx_obj.last_timestamp if last_tx_obj else None
                )

                # 2. Filter candidates by timestamp
                candidate_deposits = [
                    d
                    for d in deposits
                    if not last_known_timestamp
                    or d["block_timestamp"] > last_known_timestamp
                ]

                if not candidate_deposits:
                    return []

                # 3. Filter out already processed transactions by hash
                existing_hashes_results = await session.execute(
                    select(Transaction.tx_hash).where(
                        Transaction.user_id == user_id,
                        Transaction.tx_hash.in_(
                            [d["hash"] for d in candidate_deposits]
                        ),
                    )
                )
                existing_hashes = {h for h in existing_hashes_results.scalars()}
                truly_new_deposits = [
                    d for d in candidate_deposits if d["hash"] not in existing_hashes
                ]

                # 4. If new deposits found, process them
                if truly_new_deposits:
                    latest_timestamp = max(
                        d["block_timestamp"] for d in truly_new_deposits
                    )

                    # Update or create LastTx
                    if last_tx_obj:
                        last_tx_obj.last_timestamp = latest_timestamp
                    else:
                        session.add(
                            LastTx(user_id=user_id, last_timestamp=latest_timestamp)
                        )

                    # Add new transactions to DB
                    for d in truly_new_deposits:
                        session.add(
                            Transaction(
                                user_id=user_id,
                                token_address=d.get("token_address", ""),
                                token_symbol=d.get("token_symbol", "UNKNOWN"),
                                amount=d.get("amount_raw", "0"),
                                tx_hash=d.get("hash", ""),
                                block_timestamp=d.get("block_timestamp", ""),
                                from_address=d.get("from_address", ""),
                            )
                        )
                    logger.info(
                        f"Nuevos depósitos guardados para {user_id}. Último timestamp: {latest_timestamp}"
                    )

    except Exception as e:
        logger.error(
            f"Error procesando depósitos para el usuario {user_id}: {e}", exc_info=True
        )
        return []  # Return empty list on error

    return truly_new_deposits
