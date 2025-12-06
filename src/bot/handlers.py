import aiohttp
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from functools import partial
from src.models import (
    AsyncSessionLocal,
    User,
    UserToken,
    LastTx,
)
from sqlalchemy import delete
from src.watcher.moralis import (
    get_wallet_token_balances,
    get_token_metadata,
)
from src.services import check_and_process_deposits  # Importar el nuevo servicio
from src.utils.decorators import require_wallet  # Importar el decorador
from src.utils.format import format_deposit_msg, escape_md2
from sqlalchemy import select, func
import re
from decimal import Decimal
from src.config.logger_config import logger  # Importar el logger

# Definir estados para conversaciones
ADDTOKEN_CUSTOM_SYMBOL = 1
REMOVETOKEN_CONFIRM_ALL = 2

# Lista de comandos para el menú de Telegram y el mensaje de ayuda
BOT_COMMANDS = [
    {
        "command": "start",
        "description": "Inicia el bot y muestra un mensaje de bienvenida.",
    },
    {"command": "help", "description": "Muestra esta lista de comandos."},
    {
        "command": "setwallet",
        "description": "Configura la dirección de tu wallet para monitorizar.",
    },
    {"command": "wallet", "description": "Muestra tu dirección de wallet configurada."},
    {"command": "addtoken", "description": "Añade un token ERC-20 para monitorizar."},
    {
        "command": "removetoken",
        "description": "Elimina un token (o todos) de tu lista.",
    },
    {
        "command": "tokens",
        "description": "Muestra la lista de tokens que estás monitorizando.",
    },
    {
        "command": "check",
        "description": "Comprueba manualmente si hay nuevos depósitos para tu wallet y tokens monitorizados.",
    },
    {
        "command": "stats",
        "description": "Muestra un resumen de tus depósitos totales por token.",
    },
    {
        "command": "reset",
        "description": "Resetea el almacenamiento de la última transacción vista (solo para pruebas).",
    },
    {
        "command": "cancel",
        "description": "Cancela cualquier operación en curso.",
    },  # Añadido /cancel a la lista de comandos
]

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


@require_wallet
async def add_token_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client_session: aiohttp.ClientSession,
    user: User,  # Inyectado por el decorador
):
    user_id = update.effective_user.id
    logger.info(
        f"Comando /addtoken (inicio conversación) recibido de usuario {user_id} con args: {context.args}"
    )

    if len(context.args) != 1:
        await update.message.reply_text("Uso: /addtoken <contract_address>")
        return ConversationHandler.END

    token_address = context.args[0].lower()

    if not ERC20_ADDRESS_PATTERN.match(token_address):
        await update.message.reply_text(
            "❌ Dirección de contrato inválida. Asegúrate de que sea una dirección Ethereum/Polygon ERC-20 válida (ej. 0x...)."
        )
        return ConversationHandler.END

    try:
        async with AsyncSessionLocal() as session:
            existing_token = await session.get(UserToken, (user_id, token_address))
            if existing_token:
                display_symbol = (
                    existing_token.token_symbol
                    if existing_token.token_symbol
                    else token_address
                )
                await update.message.reply_text(
                    f"Ya estás monitorizando el token: {display_symbol} ({token_address})"
                )
                return ConversationHandler.END

            try:
                # Pasar la wallet_address del usuario a la función
                metadata = await get_token_metadata(
                    user.wallet_address, token_address, client_session
                )
                if metadata and metadata.get("symbol"):
                    token_symbol = metadata["symbol"]
                    logger.debug(
                        f"Metadatos del token {token_address} obtenidos: {metadata}. Símbolo: {token_symbol}"
                    )

                    new_user_token = UserToken(
                        user_id=user_id,
                        token_address=token_address,
                        token_symbol=token_symbol,
                    )
                    session.add(new_user_token)
                    await session.commit()
                    logger.info(
                        f"Token {token_symbol} ({token_address}) añadido para monitorización por {user_id}."
                    )
                    await update.message.reply_text(
                        f"✅ Token {token_symbol} ({token_address}) añadido para monitorización."
                    )
                    return ConversationHandler.END
                else:
                    logger.warning(
                        f"No se pudieron obtener metadatos para {token_address}. Pidiendo símbolo personalizado."
                    )
                    context.user_data["add_token_address"] = token_address
                    await update.message.reply_text(
                        "⚠️ No se pudo encontrar el símbolo para el token. \n\n"
                        "Por favor, introduce un nombre personalizado para este token (máx. 10 caracteres) o envía /cancel para cancelar."
                    )
                    return ADDTOKEN_CUSTOM_SYMBOL

            except Exception as e:
                logger.error(
                    f"Error al obtener metadatos para {token_address}: {e}",
                    exc_info=True,
                )
                await update.message.reply_text(
                    f"❌ Error al verificar el token {token_address}. Inténtalo de nuevo."
                )
                return ConversationHandler.END

    except Exception as e:
        logger.error(
            f"Error en add_token_start para usuario {user_id}: {e}", exc_info=True
        )
        await update.message.reply_text(
            "❌ Error al iniciar el proceso de añadir token. Inténtalo de nuevo."
        )
        return ConversationHandler.END


async def add_token_custom_symbol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token_address = context.user_data.get("add_token_address")
    custom_symbol = update.message.text

    logger.info(
        f"Símbolo personalizado '{custom_symbol}' recibido de {user_id} para el token {token_address}"
    )

    if not token_address:
        await update.message.reply_text(
            "Ha ocurrido un error, por favor inicia de nuevo con /addtoken."
        )
        return ConversationHandler.END

    if len(custom_symbol) > 10:
        await update.message.reply_text(
            "El nombre es demasiado largo (máx. 10 caracteres). Por favor, inténtalo de nuevo o envía /cancel."
        )
        return ADDTOKEN_CUSTOM_SYMBOL

    try:
        async with AsyncSessionLocal() as session:
            new_user_token = UserToken(
                user_id=user_id,
                token_address=token_address,
                token_symbol=custom_symbol.upper(),
            )
            session.add(new_user_token)
            await session.commit()
            logger.info(
                f"Token {custom_symbol.upper()} ({token_address}) añadido para monitorización por {user_id}."
            )
            await update.message.reply_text(
                f"✅ Token {custom_symbol.upper()} ({token_address}) añadido con tu nombre personalizado."
            )
    except Exception as e:
        logger.error(
            f"Error en add_token_custom_symbol para usuario {user_id}: {e}",
            exc_info=True,
        )
        await update.message.reply_text(
            "❌ Error al guardar el token. Inténtalo de nuevo con /addtoken."
        )
    finally:
        # Limpiar user_data
        if "add_token_address" in context.user_data:
            del context.user_data["add_token_address"]

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Usuario {user_id} ha cancelado una operación.")

    # Limpieza genérica de datos de conversación
    if "add_token_address" in context.user_data:
        del context.user_data["add_token_address"]

    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


@require_wallet
async def remove_token_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user: User
):
    user_id = user.user_id  # Usar el user_id del objeto User inyectado
    logger.info(
        f"Comando /removetoken (inicio conversación) recibido de usuario {user_id} con args: {context.args}"
    )

    if not context.args:
        await update.message.reply_text(
            "Uso: /removetoken <contract_address> o /removetoken all"
        )
        return ConversationHandler.END

    arg = context.args[0].lower()

    if arg == "all":
        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                select(func.count(UserToken.token_address)).where(
                    UserToken.user_id == user_id
                )
            )
            if count == 0:
                await update.message.reply_text("No estás monitorizando ningún token.")
                return ConversationHandler.END

        await update.message.reply_text(
            f"⚠️ ¿Estás seguro de que quieres eliminar tus {count} tokens monitorizados? Esta acción no se puede deshacer.\n\n"
            "Responde 'sí' para confirmar, o /cancel para anular."
        )
        return REMOVETOKEN_CONFIRM_ALL

    # Lógica para eliminar un solo token
    token_address = arg
    if not ERC20_ADDRESS_PATTERN.match(token_address):
        await update.message.reply_text(
            "❌ Dirección de contrato inválida. Asegúrate de que sea una dirección Ethereum/Polygon ERC-20 válida (ej. 0x...)."
        )
        return ConversationHandler.END

    try:
        async with AsyncSessionLocal() as session:
            token_to_delete = await session.get(UserToken, (user_id, token_address))
            if token_to_delete:
                token_symbol = token_to_delete.token_symbol or token_address
                await session.delete(token_to_delete)
                await session.commit()
                logger.info(
                    f"Token {token_symbol} ({token_address}) eliminado para el usuario {user_id}."
                )
                await update.message.reply_text(
                    f"✅ Token {token_symbol} ({token_address}) eliminado de tu lista."
                )
            else:
                logger.info(
                    f"Usuario {user_id} intentó eliminar el token {token_address} pero no lo estaba monitorizando."
                )
                await update.message.reply_text(
                    f"No estás monitorizando el token: {token_address}"
                )
    except Exception as e:
        logger.error(
            f"Error en remove_token (single) para usuario {user_id}: {e}", exc_info=True
        )
        await update.message.reply_text(
            "❌ Error al eliminar el token. Inténtalo de nuevo."
        )

    return ConversationHandler.END


async def remove_all_tokens_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if update.message.text.lower() != "si":
        await update.message.reply_text(
            "Operación cancelada. Tus tokens no han sido eliminados."
        )
        return ConversationHandler.END

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserToken).where(UserToken.user_id == user_id)
            )
            tokens_to_delete = result.scalars().all()

            if not tokens_to_delete:
                await update.message.reply_text("No tenías tokens para eliminar.")
                return ConversationHandler.END

            for token in tokens_to_delete:
                await session.delete(token)

            await session.commit()
            logger.info(
                f"Todos los tokens han sido eliminados para el usuario {user_id}."
            )
            await update.message.reply_text(
                "✅ Todos tus tokens monitorizados han sido eliminados."
            )

    except Exception as e:
        logger.error(
            f"Error en remove_all_tokens_confirm para usuario {user_id}: {e}",
            exc_info=True,
        )
        await update.message.reply_text(
            "❌ Error al eliminar tus tokens. Inténtalo de nuevo."
        )

    return ConversationHandler.END


@require_wallet
async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client_session: aiohttp.ClientSession,
    user: User,  # Inyectado por el decorador
):
    user_id = user.user_id
    wallet_address = user.wallet_address  # Usar la wallet del objeto User inyectado
    logger.info(f"Comando /stats recibido de usuario {user_id}")
    try:
        token_addresses_to_monitor = set()
        async with AsyncSessionLocal() as session:
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
        logger.debug(
            f"Iniciando llamada a Moralis para obtener balances para {user_id}..."
        )
        token_balances = await get_wallet_token_balances(wallet_address, client_session)
        logger.debug(
            f"Llamada a Moralis get_wallet_token_balances completada para {user_id}."
        )

        if not token_balances:
            logger.info(
                f"No se encontraron balances de tokens para la wallet {wallet_address} de {user_id}."
            )
            await update.message.reply_text(
                "No se encontraron balances de tokens para tu wallet."
            )
            return

        summary_lines = []
        total_net_worth_usd = Decimal(0)  # Initialize total net worth

        for token in token_balances:
            token_address = token.get("token_address")
            if token_address not in token_addresses_to_monitor:
                continue

            balance_raw = token.get("balance", "0")
            decimals = token.get("decimals", 18)
            symbol = token.get("symbol", "N/A")
            usd_value = token.get("usd_value", 0)  # Get USD value from the response

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
                logger.error(
                    f"Error sumando usd_value para token {symbol}: {e}", exc_info=True
                )

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
        # NOTA: Este valor es solo para los tokens monitorizados.
        try:
            formatted_net_worth = f"{total_net_worth_usd:,.2f}"
            msg += f"\n\n*Valor Total Estimado \\(USD\\) \\(Solo monitorizados\\):* ${escape_md2(formatted_net_worth)}"
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


async def check_deposits(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    client_session: aiohttp.ClientSession,
):
    user_id = update.effective_user.id
    logger.info(f"Comando /check recibido de usuario {user_id}")
    await update.message.reply_text("Buscando nuevos depósitos...")

    try:
        # Llamada al servicio centralizado
        new_deposits = await check_and_process_deposits(user_id, client_session)

        if new_deposits:
            logger.info(
                f"Enviando notificaciones para /check de {user_id}: {len(new_deposits)}"
            )
            for d in new_deposits:
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
            "❌ Error al comprobar los depósitos. La API podría estar inaccesible."
        )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Comando /reset recibido de usuario {user_id}")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.execute(delete(LastTx).where(LastTx.user_id == user_id))
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


@require_wallet
async def tokens_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user: User
):
    user_id = user.user_id  # Usar el user_id del objeto User inyectado
    logger.info(f"Comando /tokens recibido de usuario {user_id}")
    try:
        async with AsyncSessionLocal() as session:
            tracked_tokens_results = await session.execute(
                select(UserToken.token_address, UserToken.token_symbol).where(
                    UserToken.user_id == user_id
                )
            )
            tracked_tokens_data = (
                tracked_tokens_results.all()
            )  # Fetch as list of (token_address, token_symbol) tuples
            logger.debug(f"Tokens monitorizados por {user_id}: {tracked_tokens_data}")

            if tracked_tokens_data:
                token_list_msg = "Tokens monitorizados:\n"
                for token_address, token_symbol in tracked_tokens_data:
                    display_symbol = token_symbol if token_symbol else "UNKNOWN"
                    escaped_display_symbol = escape_md2(display_symbol)
                    escaped_token_address = escape_md2(token_address)
                    token_list_msg += (
                        f"\\- *{escaped_display_symbol}*: `{escaped_token_address}`\n"
                    )
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


def get_handlers(client_session: aiohttp.ClientSession):
    add_token_handler = ConversationHandler(
        entry_points=[
            CommandHandler(
                "addtoken", partial(add_token_start, client_session=client_session)
            )
        ],
        states={
            ADDTOKEN_CUSTOM_SYMBOL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_token_custom_symbol)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    remove_token_handler = ConversationHandler(
        entry_points=[CommandHandler("removetoken", remove_token_start)],
        states={
            REMOVETOKEN_CONFIRM_ALL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, remove_all_tokens_confirm
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    return [
        CommandHandler("start", start),
        CommandHandler("help", help_command),
        CommandHandler("setwallet", set_wallet),
        CommandHandler("wallet", wallet_command),
        add_token_handler,
        remove_token_handler,
        CommandHandler("tokens", tokens_command),
        CommandHandler("check", partial(check_deposits, client_session=client_session)),
        CommandHandler("stats", partial(stats, client_session=client_session)),
        CommandHandler("reset", reset),
    ]


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /help recibido de usuario {update.effective_user.id}")

    help_message_lines = ["Comandos disponibles:"]
    for cmd_info in BOT_COMMANDS:
        help_message_lines.append(f"/{cmd_info['command']} - {cmd_info['description']}")
    help_message = "\n".join(help_message_lines)

    await update.message.reply_text(help_message)
    logger.info(
        f"Comando /help ejecutado con éxito para usuario {update.effective_user.id}."
    )
