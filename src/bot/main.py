import aiohttp
import asyncio
from telegram.ext import Application
from telegram import Bot, BotCommand  # Importar BotCommand
from src.bot.handlers import get_handlers, BOT_COMMANDS  # Importar BOT_COMMANDS
from src.config.settings import settings
from src.models import engine, Base, User, AsyncSessionLocal, UserToken, Transaction
from src.watcher.moralis import get_myst_deposits
from src.watcher.storage import TxStorage
from src.utils.format import format_deposit_msg
from sqlalchemy import select
from src.config.logger_config import logger  # Importar el logger


async def init_db():
    logger.info("Inicializando la base de datos...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Base de datos inicializada.")


async def polling_job(
    bot: Bot, poll_interval: int, client_session: aiohttp.ClientSession
):
    """Tarea en segundo plano para el sondeo periódico de depósitos."""
    while True:
        logger.info("Ejecutando sondeo automático...")
        try:
            # Step 1: Fetch all users in a clean, read-only session
            all_users = []
            async with AsyncSessionLocal() as session:
                users_result = await session.execute(select(User))
                all_users = users_result.scalars().all()
            logger.debug(f"Usuarios encontrados para sondeo: {len(all_users)}")

            # Step 2: Process each user
            for user_row in all_users:
                user_id = user_row.user_id
                wallet_address = user_row.wallet_address
                logger.debug(
                    f"Procesando usuario {user_id} con wallet {wallet_address}"
                )

                try:
                    # === BLOCK 1: Read-only operations to get data for API call ===
                    token_addresses_to_monitor = []
                    async with AsyncSessionLocal() as session:
                        tokens_result = await session.execute(
                            select(UserToken.token_address).where(
                                UserToken.user_id == user_id
                            )
                        )
                        token_addresses_to_monitor = list(tokens_result.scalars())
                    logger.debug(
                        f"Tokens a monitorizar para {user_id}: {token_addresses_to_monitor}"
                    )

                    if not token_addresses_to_monitor:
                        logger.info(
                            f"Usuario {user_id} no monitoriza ningún token. Saltando."
                        )
                        continue

                    # === EXTERNAL API CALL ===
                    deposits = await get_myst_deposits(
                        wallet_address, token_addresses_to_monitor, client_session
                    )
                    logger.debug(
                        f"Depósitos obtenidos de Moralis para {user_id}: {len(deposits)}"
                    )
                    if not deposits:
                        logger.info(
                            f"No se encontraron depósitos en Moralis para {user_id}."
                        )
                        continue

                    # === BLOCK 2: Read/Write operations in a single, clean transaction ===
                    truly_new_deposits = []
                    async with AsyncSessionLocal() as session:
                        async with session.begin():  # Start a single transaction for all DB ops
                            storage = TxStorage(user_id=user_id)
                            last_known_timestamp = await storage.load_last(session)
                            logger.debug(
                                f"Último timestamp conocido para {user_id}: {last_known_timestamp}"
                            )

                            candidate_deposits = [
                                d
                                for d in deposits
                                if not last_known_timestamp
                                or d["block_timestamp"] > last_known_timestamp
                            ]
                            logger.debug(
                                f"Depósitos candidatos para {user_id} (filtrados por timestamp): {len(candidate_deposits)}"
                            )

                            if candidate_deposits:
                                existing_hashes_results = await session.execute(
                                    select(Transaction.tx_hash).where(
                                        Transaction.user_id == user_id,
                                        Transaction.tx_hash.in_(
                                            [d["hash"] for d in candidate_deposits]
                                        ),
                                    )
                                )
                                existing_hashes = {
                                    h for h in existing_hashes_results.scalars()
                                }
                                truly_new_deposits = [
                                    d
                                    for d in candidate_deposits
                                    if d["hash"] not in existing_hashes
                                ]
                                logger.debug(
                                    f"Depósitos verdaderamente nuevos para {user_id}: {len(truly_new_deposits)}"
                                )

                            if truly_new_deposits:
                                latest = max(
                                    d["block_timestamp"] for d in truly_new_deposits
                                )
                                await storage.save_last(session, latest)

                                for d in truly_new_deposits:
                                    new_tx = Transaction(
                                        user_id=user_id,
                                        token_address=d.get("token_address", ""),
                                        token_symbol=d.get("token_symbol", "UNKNOWN"),
                                        amount=d.get("amount_raw", "0"),
                                        tx_hash=d.get("hash", ""),
                                        block_timestamp=d.get("block_timestamp", ""),
                                        from_address=d.get("from_address", ""),
                                    )
                                    session.add(new_tx)
                                logger.info(
                                    f"DB actualizada para {user_id}. Última transacción: {latest}"
                                )

                            elif candidate_deposits:
                                # This case handles when LastTx is out of sync but no new tx found
                                latest = max(
                                    d["block_timestamp"] for d in candidate_deposits
                                )
                                await storage.save_last(session, latest)
                                logger.info(
                                    f"LastTx desincronizado para {user_id}. Actualizando a {latest} sin nuevos depósitos."
                                )

                    # === AFTER-COMMIT OPERATIONS ===
                    if truly_new_deposits:
                        logger.info(
                            f"Enviando {len(truly_new_deposits)} notificaciones para {user_id}"
                        )
                        for d in truly_new_deposits:
                            msg = format_deposit_msg(d)
                            await bot.send_message(
                                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
                            )
                    else:
                        logger.info(f"No hay transacciones nuevas para {user_id}")

                except Exception as e:
                    logger.error(
                        f"ERROR en polling_job para user {user_id} ({wallet_address}): {e}",
                        exc_info=True,  # Registra el traceback completo
                    )
                    # Opcional: enviar un mensaje de error al usuario si el problema es persistente
                    # await bot.send_message(chat_id=user_id, text=f"❌ Hubo un error al comprobar tus depósitos: {e}")

        except Exception as e:
            logger.error(f"ERROR general en polling_job: {e}", exc_info=True)

        await asyncio.sleep(poll_interval)


async def main():
    logger.info("Iniciando Token Tracker Bot...")
    await init_db()  # Inicializar la base de datos
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30)
    ) as client_session:
        app = Application.builder().token(settings.telegram_token).build()

        # Crear una instancia de Bot para el polling_job
        bot_instance = Bot(settings.telegram_token)

        for handler in get_handlers(client_session):
            app.add_handler(handler)
        logger.info("Handlers del bot cargados.")

        await app.initialize()
        await app.start()
        logger.info("Telegram bot iniciado (polling para comandos).")

        # Establecer los comandos del bot para el menú de Telegram
        await app.bot.set_my_commands(
            [BotCommand(cmd["command"], cmd["description"]) for cmd in BOT_COMMANDS]
        )
        logger.info("Comandos del bot establecidos en el menú de Telegram.")

        # Iniciar la tarea de sondeo en segundo plano
        asyncio.create_task(
            polling_job(bot_instance, settings.poll_interval, client_session)
        )
        logger.info(
            f"Tarea de sondeo en segundo plano iniciada con intervalo de {settings.poll_interval} segundos."
        )

        await app.updater.start_polling()  # Polling Telegram (no blockchain)
        await asyncio.Event().wait()  # Run forever
        logger.info("Bot detenido.")


if __name__ == "__main__":
    asyncio.run(main())
