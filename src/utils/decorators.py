# src/utils/decorators.py
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from src.models import AsyncSessionLocal, User
from src.config.logger_config import logger


def require_wallet(handler):
    @wraps(handler)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user_id = update.effective_user.id
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user or not user.wallet_address:
                logger.info(
                    f"Usuario {user_id} intentó usar un comando sin wallet configurada."
                )
                await update.message.reply_text(
                    "Primero debes configurar tu wallet con /setwallet."
                )
                if isinstance(
                    handler, ConversationHandler
                ):  # Check if it's a conversation handler entry point
                    return ConversationHandler.END
                return
            # Pass the user object to the handler
            kwargs["user"] = user
            return await handler(update, context, *args, **kwargs)

    return wrapper
