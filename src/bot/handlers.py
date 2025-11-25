import sys
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from src.models import (
    AsyncSessionLocal,
    User,
    UserToken,
    Transaction,
)  # Importar Transaction
from src.watcher.storage import TxStorage
from src.watcher.moralis import get_myst_deposits  # Added import
from src.utils.format import format_deposit_msg, escape_md2  # Added import
from sqlalchemy import select, func, cast, Numeric, REAL  # Importar func, cast, Numeric, REAL para agregaciones y casting
import re
from decimal import Decimal

# Patrón regex para validar una dirección ERC-20 (0x + 40 caracteres hexadecimales)
ERC20_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenido al Token Tracker Bot! Usa /setwallet <address> y /check para depósitos MYST."
    )


async def set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /setwallet <tu_address>")
        return

    wallet = context.args[0].lower()

    # Validar el formato de la wallet
    if not ERC20_ADDRESS_PATTERN.match(wallet):
        await update.message.reply_text(
            "❌ Dirección de wallet inválida. Asegúrate de que sea una dirección Ethereum/Polygon ERC-20 válida (ej. 0x...)."
        )
        return

    user_id = update.effective_user.id

    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                user = await session.get(User, user_id)
                if user:
                    user.wallet_address = wallet
                else:
                    user = User(user_id=user_id, wallet_address=wallet)
                    session.add(user)
                await session.commit()
        await update.message.reply_text(f"Wallet set: {wallet}")
    except Exception as e:
        print(f"ERROR en set_wallet: {e}", file=sys.stderr)
        await update.message.reply_text(
            "❌ Error al guardar la wallet. Inténtalo de nuevo."
        )


async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /addtoken <contract_address>")
        return

    token_address = context.args[0].lower()

    # Validar el formato de la dirección del token
    if not ERC20_ADDRESS_PATTERN.match(token_address):
        await update.message.reply_text(
            "❌ Dirección de contrato inválida. Asegúrate de que sea una dirección Ethereum/Polygon ERC-20 válida (ej. 0x...)."
        )
        return

    user_id = update.effective_user.id

    try:
        async with AsyncSessionLocal() as session:
            # Verificar si el usuario ya existe
            user = await session.get(User, user_id)
            if not user:
                await update.message.reply_text(
                    "Primero debes configurar tu wallet con /setwallet."
                )
                return

            # Verificar si el token ya está siendo trackeado
            existing_token = await session.get(UserToken, (user_id, token_address))
            if existing_token:
                await update.message.reply_text(
                    f"Ya estás monitorizando el token: {token_address}"
                )
                return

            new_user_token = UserToken(user_id=user_id, token_address=token_address)
            session.add(new_user_token)
            await session.commit()
        await update.message.reply_text(
            f"Token {token_address} añadido para monitorización."
        )
    except Exception as e:
        print(f"ERROR en add_token: {e}", file=sys.stderr)
        await update.message.reply_text(
            "❌ Error al añadir el token. Inténtalo de nuevo."
        )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        async with AsyncSessionLocal() as session:
            # Verificar si el usuario ha configurado una wallet
            user = await session.get(User, user_id)
            if not user:
                await update.message.reply_text(
                    "Primero debes configurar tu wallet con /setwallet."
                )
                return

            # Obtener y sumar transacciones por token
            total_by_token = await session.execute(
                select(
                    Transaction.token_symbol,
                    Transaction.token_address,
                    func.sum(cast(Transaction.amount, REAL)).label("total_amount"),
                )
                .where(Transaction.user_id == user_id)
                .group_by(Transaction.token_address, Transaction.token_symbol)
            )

            summary_lines = []
            DEFAULT_TOKEN_DECIMALS = 18 # Assuming 18 decimals for ERC-20 tokens like MYST

            for symbol, address, total_amount_float in total_by_token:
                # Convert float total_amount to Decimal for precise calculation
                total_amount_decimal = Decimal(str(total_amount_float)) / (10 ** DEFAULT_TOKEN_DECIMALS)
                
                # Format to a readable string, e.g., 8 decimal places
                formatted_amount = f"{total_amount_decimal:.8f}".rstrip("0").rstrip(".")

                escaped_symbol = escape_md2(symbol or "")
                escaped_address_snippet = escape_md2(address[:10])
                escaped_formatted_amount = escape_md2(formatted_amount)
                
                summary_lines.append(
                    f"• {escaped_symbol or escaped_address_snippet}: {escaped_formatted_amount} \\(total\\)"
                )

            if not summary_lines:
                await update.message.reply_text("Aún no tienes depósitos registrados.")
                return

            msg = "📊 *Resumen de Depósitos:*\n\n" + "\n".join(summary_lines)
            await update.message.reply_markdown_v2(msg)

    except Exception as e:
        print(f"ERROR en stats: {e}", file=sys.stderr)
        await update.message.reply_text(
            "❌ Error al obtener tus estadísticas de depósitos. Inténtalo de nuevo."
        )


async def check_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():  # Start a single transaction for all DB operations
                user = await session.get(User, user_id)
                if not user:
                    await update.message.reply_text("Set wallet primero con /setwallet")
                    return
                wallet_address = user.wallet_address

                # Obtener los tokens que el usuario quiere monitorizar
                tracked_tokens_results = await session.execute(
                    select(UserToken.token_address).where(UserToken.user_id == user_id)
                )
                token_addresses_to_monitor = [
                    token for token in tracked_tokens_results.scalars()
                ]

            if not token_addresses_to_monitor:
                await update.message.reply_text(
                    "No estás monitorizando ningún token. Usa /addtoken <contract_address> para añadir uno."
                )
                return

            storage = TxStorage(user_id=user_id)
            deposits = await get_myst_deposits(
                wallet_address, token_addresses_to_monitor
            )
            new_deposits = await storage.filter_new(session, deposits)

            if not new_deposits:  # Moved this check here, outside the transaction block
                await update.message.reply_text(
                    "No hay depósitos nuevos de los tokens monitorizados."
                )
                return

            # All write operations in a transaction
            async with session.begin():
                latest = max(d["block_timestamp"] for d in new_deposits)

                await storage.save_last(session, latest)
                print(f"Última transacción guardada: {latest}")

                for d in new_deposits:
                    new_tx = Transaction(
                        user_id=user_id,
                        token_address=d.get("token_address", ""),
                        token_symbol=d.get("token_symbol", "UNKNOWN"),
                        amount=d.get("amount_raw", "0"),
                        tx_hash=d.get("tx_hash", ""),
                        block_timestamp=d.get("block_timestamp", ""),
                        from_address=d.get("from_address", ""),
                    )
                    session.add(new_tx)

            # Send messages after commit
            for d in new_deposits:
                msg = format_deposit_msg(d)
                await update.message.reply_markdown_v2(msg)

        # The session and transaction are managed by the outer async with blocks.
        # No 'else' block needed here for "no new deposits" as it's handled inside the 'if' and 'if not token_addresses_to_monitor'

    except Exception as e:
        print(f"ERROR en check_deposits: {e}", file=sys.stderr)
        await update.message.reply_text(
            "❌ Error al comprobar los depósitos. La API de Moralis podría estar inaccesible o la wallet es incorrecta."
        )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():  # Asegurar una transacción
                storage = TxStorage(user_id=user_id)
                await storage.reset(session)  # Pasar la sesión
        await update.message.reply_text(
            "🔄 Storage reseteado\n"
            "La próxima vez que hagas /check verás las transacciones nuevamente"
        )
    except Exception as e:
        print(f"ERROR en reset para user {user_id}: {e}", file=sys.stderr)
        await update.message.reply_text(
            "❌ Error al resetear el almacenamiento. Inténtalo de nuevo."
        )


# Handlers para app (en main.py)
def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("setwallet", set_wallet),
        CommandHandler("check", check_deposits),
        CommandHandler("addtoken", add_token),  # Añadir el nuevo handler
        CommandHandler("stats", stats),  # Añadir el nuevo handler /stats
        CommandHandler("reset", reset),  # temporal - test
    ]
