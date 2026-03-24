"""
Telegram Bot — главный файл запуска
"""

import asyncio
import logging
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import user, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)


async def health(request):
    return web.Response(text="OK")


async def run_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    logger.info("Health check сервер запущен на порту 8000")


async def self_ping():
    """Пингует себя каждые 5 минут чтобы сервер не засыпал."""
    app_url = os.environ.get("APP_URL", "")
    if not app_url:
        logger.info("APP_URL не задан — self-ping отключён")
        return
    await asyncio.sleep(30)  # ждём пока сервер поднимется
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{app_url}/") as resp:
                    logger.info(f"Self-ping: {resp.status}")
        except Exception as e:
            logger.warning(f"Self-ping ошибка: {e}")
        await asyncio.sleep(300)  # каждые 5 минут


async def run_bot():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(user.router)
    logger.info("Бот запущен и слушает обновления...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def main():
    logger.info("Запуск бота...")
    await asyncio.gather(run_web(), run_bot(), self_ping())


if __name__ == "__main__":
    asyncio.run(main())
