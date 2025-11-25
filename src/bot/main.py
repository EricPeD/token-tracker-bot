import asyncio
from telegram.ext import Application
from telegram import Bot
from src.bot.handlers import get_handlers
from src.config.settings import settings
from src.models import engine, Base, User, AsyncSessionLocal, UserToken, Transaction
from src.watcher.moralis import get_myst_deposits
from src.watcher.storage import TxStorage
from src.utils.format import format_deposit_msg
from sqlalchemy import select # Importar select
import sys

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def polling_job(bot: Bot, poll_interval: int):
    """Tarea en segundo plano para el sondeo periódico de depósitos."""
    while True:
        print(f"[{asyncio.get_event_loop().time()}] Ejecutando sondeo automático...")
        try:
            # Step 1: Fetch all users in a clean, read-only session
            all_users = []
            async with AsyncSessionLocal() as session:
                users_result = await session.execute(select(User))
                all_users = users_result.scalars().all()

            # Step 2: Process each user in their own session and transaction
            for user_row in all_users:
                user_id = user_row.user_id
                wallet_address = user_row.wallet_address
                
                try:
                    async with AsyncSessionLocal() as session_per_user: # New session for this user
                        async with session_per_user.begin(): # Transaction for this user's operations
                            # All database operations for this user go here
                            # Obtener los tokens que el usuario quiere monitorizar
                            tracked_tokens_results = await session_per_user.execute(
                                select(UserToken.token_address)
                                .where(UserToken.user_id == user_id)
                            )
                            token_addresses_to_monitor = [token for token in tracked_tokens_results.scalars()]

                            if not token_addresses_to_monitor:
                                print(f"[{asyncio.get_event_loop().time()}] Usuario {user_id} no monitoriza ningún token. Saltando.")
                                # This will cause the transaction to rollback if not committed. This is correct behavior for a skipped user.
                                continue 

                            storage = TxStorage(user_id=user_id)
                            deposits = await get_myst_deposits(wallet_address, token_addresses_to_monitor)
                            new_deposits = await storage.filter_new(session_per_user, deposits) # Pass session_per_user

                            if new_deposits:
                                latest = max(d["block_timestamp"] for d in new_deposits)
                                
                                await storage.save_last(session_per_user, latest)
                                print(f"[{asyncio.get_event_loop().time()}] Última transacción guardada para {user_id}: {latest}")

                                for d in new_deposits:
                                    new_tx = Transaction(
                                        user_id=user_id,
                                        token_address=d.get("token_address", ""),
                                        token_symbol=d.get("token_symbol", "UNKNOWN"),
                                        amount=d.get("amount_raw", "0"),
                                        tx_hash=d.get("tx_hash", ""),
                                        block_timestamp=d.get("block_timestamp", ""),
                                        from_address=d.get("from_address", "")
                                    )
                                    session_per_user.add(new_tx)
                                # Transaction commits here on successful exit of begin() block
                                
                                print(f"[{asyncio.get_event_loop().time()}] Nuevos depósitos para {user_id}: {len(new_deposits)}")
                                for d in new_deposits:
                                    msg = format_deposit_msg(d)
                                    await bot.send_message(chat_id=user_id, text=msg, parse_mode='MarkdownV2')
                            else:
                                print(f"[{asyncio.get_event_loop().time()}] No hay transacciones nuevas para {user_id} → no se actualiza storage")
                        # session_per_user closes here
                except Exception as e:
                    print(f"ERROR en polling_job para user {user_id} ({wallet_address}): {e}", file=sys.stderr)
                    # Opcional: enviar un mensaje de error al usuario si el problema es persistente
                    # await bot.send_message(chat_id=user_id, text=f"❌ Hubo un error al comprobar tus depósitos: {e}")

        except Exception as e:
            print(f"ERROR general en polling_job: {e}", file=sys.stderr)
        
        await asyncio.sleep(poll_interval)


async def main():
    await init_db()  # Inicializar la base de datos
    app = Application.builder().token(settings.telegram_token).build()
    
    # Crear una instancia de Bot para el polling_job
    bot_instance = Bot(settings.telegram_token)

    for handler in get_handlers():
        app.add_handler(handler)
    
    await app.initialize()
    await app.start()
    
    # Iniciar la tarea de sondeo en segundo plano
    asyncio.create_task(polling_job(bot_instance, settings.poll_interval))

    await app.updater.start_polling()  # Polling Telegram (no blockchain)
    await asyncio.Event().wait()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
