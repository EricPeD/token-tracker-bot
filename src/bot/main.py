import aiohttp
import asyncio
from telegram.ext import Application
from telegram import Bot, BotCommand
from src.bot.handlers import get_handlers, BOT_COMMANDS
from src.config.settings import settings
from src.models import engine, Base, User, AsyncSessionLocal
from src.services import check_and_process_deposits  # Importar el nuevo servicio
from src.utils.format import format_deposit_msg
from sqlalchemy import select
from src.config.logger_config import logger


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
            all_users = []
            async with AsyncSessionLocal() as session:
                users_result = await session.execute(select(User))
                all_users = users_result.scalars().all()
            logger.debug(f"Usuarios encontrados para sondeo: {len(all_users)}")

            for user_row in all_users:
                user_id = user_row.user_id
                logger.debug(f"Procesando usuario {user_id}")

                try:
                    # Llama al servicio centralizado para hacer todo el trabajo
                    new_deposits = await check_and_process_deposits(
                        user_id, client_session
                    )

                    # La única responsabilidad que queda es notificar
                    if new_deposits:
                        logger.info(
                            f"Enviando {len(new_deposits)} notificaciones para {user_id}"
                        )
                        for d in new_deposits:
                            msg = format_deposit_msg(d)
                            await bot.send_message(
                                chat_id=user_id, text=msg, parse_mode="MarkdownV2"
                            )
                    else:
                        logger.info(f"No hay transacciones nuevas para {user_id}")

                except Exception as e:
                    logger.error(
                        f"ERROR en polling_job para user {user_id}: {e}",
                        exc_info=True,
                    )

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
