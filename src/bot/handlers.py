from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from watcher.moralis import get_myst_deposits  # Tu watcher actual
from utils.format import format_deposit_msg  # Ver abajo
from watcher.storage import TxStorage  # Ver abajo –con SQLite
from config.settings import settings

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bienvenido al Token Tracker Bot! Usa /setwallet <address> y /check para depósitos MYST.")

async def set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("Uso: /setwallet <tu_address>")
        return
    settings.wallet_address = context.args[0].lower()  # Update settings – futuro DB
    await update.message.reply_text(f"Wallet set: {settings.wallet_address}")

async def check_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not settings.wallet_address:
        await update.message.reply_text("Set wallet primero con /setwallet")
        return

    storage = TxStorage()  # Instancia storage
    deposits = await get_myst_deposits(settings.wallet_address)  # Fetch
    new_deposits = storage.filter_new(deposits)  # Filter nuevos

    if not new_deposits:
        await update.message.reply_text("No hay depósitos nuevos de MYST")
        return

    # Solo guardamos si realmente hubo transacciones nuevas
    if new_deposits:
        latest = max(d["block_timestamp"] for d in new_deposits)
        storage.save_last(latest)
        print(f"Última transacción guardada: {latest}")
    else:
        print("No hay transacciones nuevas → no se actualiza storage")

    # Envía msgs
    for d in new_deposits:
        msg = format_deposit_msg(d)
        await update.message.reply_markdown_v2(msg)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage = TxStorage(update.effective_user.id)
    storage.reset()
    await update.message.reply_text(
        "🔄 Storage reseteado\n"
        "La próxima vez que hagas /check verás las transacciones nuevamente"
    )

# Handlers para app (en main.py)
def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("setwallet", set_wallet),
        CommandHandler("check", check_deposits),
        CommandHandler("reset", reset), # temporal - test
    ]