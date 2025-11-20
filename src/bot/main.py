import asyncio
from telegram.ext import Application
from bot.handlers import get_handlers
from config.settings import settings

async def main():
    app = Application.builder().token(settings.telegram_token).build()
    for handler in get_handlers():
        app.add_handler(handler)
    await app.initialize()
    await app.start()
    await app.updater.start_polling() # Polling Telegram (no blockchain)
    await asyncio.Event().wait() # Run forever

if __name__ == "__main__":
    asyncio.run(main())