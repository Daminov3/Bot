import os
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.handlers.start import router as start_router
from app.handlers.admin import router as admin_router
from app.handlers.movie import router as movie_router

from app.database import create_tables
from app.config import BOT_TOKEN, ADMIN_ID

logging.basicConfig(level=logging.INFO)

# Render saytingiz manzili
RENDER_WEBHOOK_URL = os.getenv("RENDER_URL")
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

dp.include_router(admin_router)
dp.include_router(start_router)
dp.include_router(movie_router)

# Render portni avtomat belgilaydi
PORT = int(os.getenv("PORT", 8080))

# YANGI QO'SHILGAN FUNKSIYA: cron-job.org va brauzer uchun javob qaytaradi
async def home_handler(request):
    return web.Response(text="Bot muvaffaqiyatli ishlamoqda!")

async def on_startup(bot: Bot) -> None:
    logging.info("Bot ishga tushmoqda...")
    create_tables()

    admin_commands = [
        BotCommand(command="addmovie", description="🎬 Kino qo'shish"),
        BotCommand(command="movies", description="📂 Kinolar ro'yxati"),
        BotCommand(command="deletemovie", description="🗑 Kino o'chirish"),
        BotCommand(command="stats", description="📊 Statistika"),
        BotCommand(command="addchannel", description="📢 Kanal qo'shish"),
        BotCommand(command="channels", description="📋 Kanallar ro'yxati"),
        BotCommand(command="deletechannel", description="❌ Kanal o'chirish"),
        BotCommand(command="stop", description="⛔ Jarayonni to'xtatish"),
        BotCommand(command="import", description="📥 Backup import"),
    ]

    await bot.set_my_commands(
        commands=admin_commands,
        scope=BotCommandScopeChat(chat_id=ADMIN_ID)
    )
    
    # Telegramga xabarlarni qayerga yuborish kerakligini aytamiz
    await bot.set_webhook(url=f"{RENDER_WEBHOOK_URL}{WEBHOOK_PATH}")
    logging.info(f"Webhook o'rnatildi: {RENDER_WEBHOOK_URL}{WEBHOOK_PATH}")

def main():
    dp.startup.register(on_startup)
    app = web.Application()
    
    # YANGI QO'SHILGAN QATOR: Asosiy sahifaga so'rov kelganda home_handler ishga tushadi
    app.router.add_get('/', home_handler)
    
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
