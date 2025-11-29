import asyncio
import aiohttp
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from functools import partial
from src.models import (
    AsyncSessionLocal,
    User,
    UserToken,
    Transaction,
)
from src.watcher.storage import TxStorage
from src.watcher.moralis import (
    get_myst_deposits,
    get_wallet_token_balances,
)
from src.utils.format import format_deposit_msg, escape_md2
from sqlalchemy import select
import re
from decimal import Decimal
from src.config.logger_config import logger  # Importar el logger

# Patrón regex para validar una dirección ERC-20 (0x + 40 caracteres hexadecimales)
ERC20_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /start recibido de usuario {update.effective_user.id}")
    await update.message.reply_text(
        "Bienvenido al Token Tracker Bot! Usa /setwallet <address> y /check para depósitos MYST."
    )


async def set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(
        f"Comando /setwallet recibido de usuario {user_id} con args: {context.args}"
    )

    if len(context.args) != 1:
        logger.warning(
            f"Uso incorrecto de /setwallet por {user_id}. Args: {context.args}"
        )
        await update.message.reply_text("Uso: /setwallet <tu_address>")
        return

    wallet = context.args[0].lower()

    if not ERC20_ADDRESS_PATTERN.match(wallet):
        logger.warning(f"Wallet inválida '{wallet}' proporcionada por {user_id}")
        await update.message.reply_text(
            "❌ Dirección de wallet inválida. Asegúrate de que sea una dirección Ethereum/Polygon ERC-20 válida (ej. 0x...)."
        )
        return

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                user = await session.get(User, user_id)
                if user:
                    user.wallet_address = wallet
                    logger.info(f"Wallet actualizada para {user_id} a {wallet}")
                else:
                    user = User(user_id=user_id, wallet_address=wallet)
                    session.add(user)
                    logger.info(f"Nueva wallet establecida para {user_id}: {wallet}")
                await session.commit()
        await update.message.reply_text(f"Wallet set: {wallet}")
    except Exception as e:
        logger.error(f"Error en set_wallet para usuario {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error al guardar la wallet. Inténtalo de nuevo."
        )


async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(
        f"Comando /addtoken recibido de usuario {user_id} con args: {context.args}"
    )

    if len(context.args) != 1:
        logger.warning(
            f"Uso incorrecto de /addtoken por {user_id}. Args: {context.args}"
        )
        await update.message.reply_text("Uso: /addtoken <contract_address>")
        return

    token_address = context.args[0].lower()

    if not ERC20_ADDRESS_PATTERN.match(token_address):
        logger.warning(
            f"Dirección de token inválida '{token_address}' proporcionada por {user_id}"
        )
        await update.message.reply_text(
            "❌ Dirección de contrato inválida. Asegúrate de que sea una dirección Ethereum/Polygon ERC-20 válida (ej. 0x...)."
        )
        return

    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                logger.info(
                    f"Usuario {user_id} intentó /addtoken sin wallet configurada."
                )
                await update.message.reply_text(
                    "Primero debes configurar tu wallet con /setwallet."
                )
                return

            existing_token = await session.get(UserToken, (user_id, token_address))
            if existing_token:
                logger.info(f"Usuario {user_id} ya monitoriza el token {token_address}")
                await update.message.reply_text(
                    f"Ya estás monitorizando el token: {token_address}"
                )
                return

            new_user_token = UserToken(user_id=user_id, token_address=token_address)
            session.add(new_user_token)
            await session.commit()
            logger.info(
                f"Token {token_address} añadido para monitorización por {user_id}."
            )
        await update.message.reply_text(
            f"Token {token_address} añadido para monitorización."
        )
    except Exception as e:
        logger.error(f"Error en add_token para usuario {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error al añadir el token. Inténtalo de nuevo."
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE, client_session: aiohttp.ClientSession):
    user_id = update.effective_user.id
    logger.info(f"Comando /stats recibido de usuario {user_id}")
    try:
        wallet_address = ""
        token_addresses_to_monitor = set()
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user or not user.wallet_address:
                logger.info(f"Usuario {user_id} intentó /stats sin wallet configurada.")
                await update.message.reply_text(
                    "Primero debes configurar tu wallet con /setwallet."
                )
                return
            wallet_address = user.wallet_address

            tracked_tokens_results = await session.execute(
                select(UserToken.token_address).where(UserToken.user_id == user_id)
            )
            token_addresses_to_monitor = set(tracked_tokens_results.scalars().all())
            logger.debug(
                f"Tokens monitorizados por {user_id}: {token_addresses_to_monitor}"
            )

        if not token_addresses_to_monitor:
            logger.info(f"Usuario {user_id} intentó /stats sin tokens monitorizados.")
            await update.message.reply_text(
                "No estás monitorizando ningún token. Usa /addtoken para añadir uno y verlo en /stats."
            )
            return

        # Ejecutar solo la llamada a get_wallet_token_balances
        logger.debug(f"Iniciando llamada a Moralis para obtener balances para {user_id}...")
        token_balances = await get_wallet_token_balances(wallet_address, client_session)
        logger.debug(f"Llamada a Moralis get_wallet_token_balances completada para {user_id}.")

        if not token_balances:
            logger.info(
                f"No se encontraron balances de tokens para la wallet {wallet_address} de {user_id}."
            )
            await update.message.reply_text(
                "No se encontraron balances de tokens para tu wallet."
            )
            return

        summary_lines = []
        total_net_worth_usd = Decimal(0) # Initialize total net worth

        for token in token_balances:
            token_address = token.get("token_address")
            if token_address not in token_addresses_to_monitor:
                continue

            balance_raw = token.get("balance", "0")
            decimals = token.get("decimals", 18)
            symbol = token.get("symbol", "N/A")
            usd_value = token.get("usd_value", 0) # Get USD value from the response

            try:
                balance_decimal = Decimal(balance_raw) / (10**decimals)
                formatted_balance = f"{balance_decimal:.8f}".rstrip("0").rstrip(".")
            except Exception:
                formatted_balance = "Error"
                logger.error(
                    f"Error formateando balance {balance_raw} para token {symbol} ({decimals} decs) para {user_id}",
                    exc_info=True,
                )

            escaped_symbol = escape_md2(symbol)
            escaped_balance = escape_md2(formatted_balance)

            summary_lines.append(f"• {escaped_symbol}: {escaped_balance}")

            # Add to total net worth only for monitored tokens
            try:
                total_net_worth_usd += Decimal(str(usd_value))
            except Exception as e:
                logger.error(f"Error sumando usd_value para token {symbol}: {e}", exc_info=True)


        non_zero_balances = [line for line in summary_lines if not line.endswith(": 0")]

        if not non_zero_balances:
            logger.info(
                f"Todos los balances de los tokens monitorizados para {user_id} son 0."
            )
            await update.message.reply_text(
                "Los balances de tus tokens monitorizados son 0."
            )
            return

        # Construir el mensaje
        msg = "📊 *Balances de tu Wallet \\(Tokens Monitorizados\\):*\n\n" + "\n".join(
            non_zero_balances
        )

        # Añadir el valor neto total calculado localmente
        try:
            formatted_net_worth = f"{total_net_worth_usd:,.2f}"
            msg += f"\n\n*Valor Total Estimado \\(USD\\):* ${escape_md2(formatted_net_worth)}"
            logger.debug(
                f"Valor neto formateado para {user_id}: ${formatted_net_worth}"
            )
        except Exception as e:
            logger.error(
                f"Error formateando valor neto total calculado para {user_id}: {e}",
                exc_info=True,
            )

        await update.message.reply_markdown_v2(msg)
        logger.info(f"Comando /stats ejecutado con éxito para usuario {user_id}.")

    except Exception as e:
        logger.error(
            f"Error general en stats para usuario {user_id}: {e}", exc_info=True
        )
        await update.message.reply_text(
            "❌ Error al obtener los balances de tu wallet. Inténtalo de nuevo."
        )


async def check_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE, client_session: aiohttp.ClientSession):
    user_id = update.effective_user.id
    logger.info(f"Comando /check recibido de usuario {user_id}")
    try:
        wallet_address = None
        token_addresses_to_monitor = []
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user or not user.wallet_address:
                logger.info(f"Usuario {user_id} intentó /check sin wallet configurada.")
                await update.message.reply_text("Set wallet primero con /setwallet")
                return
            wallet_address = user.wallet_address

            tracked_tokens_results = await session.execute(
                select(UserToken.token_address).where(UserToken.user_id == user_id)
            )
            token_addresses_to_monitor = list(tracked_tokens_results.scalars())
        logger.debug(
            f"Tokens monitorizados para /check de {user_id}: {token_addresses_to_monitor}"
        )

        if not token_addresses_to_monitor:
            logger.info(f"Usuario {user_id} intentó /check sin tokens monitorizados.")
            await update.message.reply_text(
                "No estás monitorizando ningún token. Usa /addtoken <contract_address> para añadir uno."
            )
            return

        deposits = await get_myst_deposits(wallet_address, token_addresses_to_monitor, client_session)
        logger.debug(
            f"Depósitos obtenidos de Moralis para /check de {user_id}: {len(deposits)}"
        )
        if not deposits:
            logger.info(
                f"No se encontraron depósitos en Moralis para /check de {user_id}."
            )
            await update.message.reply_text(
                "No se encontraron depósitos para los tokens monitorizados."
            )
            return

        truly_new_deposits = []
        async with AsyncSessionLocal() as session:
            async with session.begin():
                storage = TxStorage(user_id=user_id)
                last_known_timestamp = await storage.load_last(session)
                logger.debug(
                    f"Último timestamp conocido para /check de {user_id}: {last_known_timestamp}"
                )

                candidate_deposits = [
                    d
                    for d in deposits
                    if not last_known_timestamp
                    or d["block_timestamp"] > last_known_timestamp
                ]
                logger.debug(
                    f"Depósitos candidatos para /check de {user_id}: {len(candidate_deposits)}"
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
                    existing_hashes = {h for h in existing_hashes_results.scalars()}
                    truly_new_deposits = [
                        d
                        for d in candidate_deposits
                        if d["hash"] not in existing_hashes
                    ]
                    logger.info(
                        f"Depósitos verdaderamente nuevos para /check de {user_id}: {len(truly_new_deposits)}"
                    )

                if truly_new_deposits:
                    latest = max(d["block_timestamp"] for d in truly_new_deposits)
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
                    logger.info(f"Nuevos depósitos guardados para /check de {user_id}.")

        if truly_new_deposits:
            logger.info(
                f"Enviando notificaciones para /check de {user_id}: {len(truly_new_deposits)}"
            )
            for d in truly_new_deposits:
                msg = format_deposit_msg(d)
                await update.message.reply_markdown_v2(msg)
        else:
            logger.info(f"No hay depósitos nuevos para /check de {user_id}.")
            await update.message.reply_text(
                "No hay depósitos nuevos de los tokens monitorizados."
            )

    except Exception as e:
        logger.error(
            f"Error general en check_deposits para usuario {user_id}: {e}",
            exc_info=True,
        )
        await update.message.reply_text(
            "❌ Error al comprobar los depósitos. La API de Moralis podría estar inaccesible o la wallet es incorrecta."
        )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Comando /reset recibido de usuario {user_id}")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                storage = TxStorage(user_id=user_id)
                await storage.reset(session)
        logger.info(f"Storage reseteado para {user_id}.")
        await update.message.reply_text(
            "🔄 Storage reseteado\n"
            "La próxima vez que hagas /check verás las transacciones nuevamente"
        )
    except Exception as e:
        logger.error(f"Error en reset para usuario {user_id}: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error al resetear el almacenamiento. Inténtalo de nuevo."
        )


async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Comando /wallet recibido de usuario {user_id}")
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if user and user.wallet_address:
                escaped_wallet = escape_md2(user.wallet_address)
                logger.debug(f"Wallet configurada para {user_id}: {escaped_wallet}")
                await update.message.reply_markdown_v2(
                    f"Tu wallet configurada es: `{escaped_wallet}`"
                )
            else:
                logger.info(
                    f"Usuario {user_id} intentó /wallet sin wallet configurada."
                )
                await update.message.reply_text(
                    "No tienes una wallet configurada. Usa /setwallet <direccion> para hacerlo."
                )
    except Exception as e:
        logger.error(
            f"Error en wallet_command para usuario {user_id}: {e}", exc_info=True
        )
        await update.message.reply_text(
            "❌ Error al obtener tu wallet. Inténtalo de nuevo."
        )


async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Comando /tokens recibido de usuario {user_id}")
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                logger.info(
                    f"Usuario {user_id} intentó /tokens sin wallet configurada."
                )
                await update.message.reply_text(
                    "Primero debes configurar tu wallet con /setwallet."
                )
                return

            tracked_tokens_results = await session.execute(
                select(UserToken.token_address).where(UserToken.user_id == user_id)
            )
            token_addresses = [token for token in tracked_tokens_results.scalars()]
            logger.debug(f"Tokens monitorizados por {user_id}: {token_addresses}")

            if token_addresses:
                token_list_msg = "Tokens monitorizados:\n"
                for token_address in token_addresses:
                    escaped_token_address = escape_md2(token_address)
                    token_list_msg += f"\\- `{escaped_token_address}`\n"
                await update.message.reply_markdown_v2(token_list_msg)
                logger.info(
                    f"Comando /tokens ejecutado con éxito para usuario {user_id}."
                )
            else:
                logger.info(f"Usuario {user_id} no monitoriza ningún token.")
                await update.message.reply_text(
                    "No estás monitorizando ningún token. Usa /addtoken <contract_address> para añadir uno."
                )
    except Exception as e:
        logger.error(
            f"Error en tokens_command para usuario {user_id}: {e}", exc_info=True
        )
        await update.message.reply_text(
            "❌ Error al obtener tus tokens. Inténtalo de nuevo."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /help recibido de usuario {update.effective_user.id}")
    help_message = (
        "Comandos disponibles:\n"
        "/start - Inicia el bot y muestra un mensaje de bienvenida.\n"
        "/help - Muestra esta lista de comandos.\n"
        "/setwallet <direccion> - Configura la dirección de tu wallet para monitorizar.\n"
        "/wallet - Muestra tu dirección de wallet configurada.\n"
        "/addtoken <direccion_contrato> - Añade un token ERC-20 para monitorizar.\n"
        "/tokens - Muestra la lista de tokens que estás monitorizando.\n"
        "/check - Comprueba manualmente si hay nuevos depósitos para tu wallet y tokens monitorizados.\n"
        "/stats - Muestra un resumen de tus depósitos totales por token.\n"
        "/reset - Resetea el almacenamiento de la última transacción vista (solo para pruebas)."
    )
    await update.message.reply_text(help_message)
    logger.info(
        f"Comando /help ejecutado con éxito para usuario {update.effective_user.id}."
    )


def get_handlers(client_session: aiohttp.ClientSession):
    return [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("setwallet", set_wallet),
        CommandHandler("wallet", wallet_command),
        CommandHandler("addtoken", add_token),
        CommandHandler("tokens", tokens_command),
        CommandHandler("check", partial(check_deposits, client_session=client_session)),
        CommandHandler("stats", partial(stats, client_session=client_session)),
        CommandHandler("reset", reset),
    ]
