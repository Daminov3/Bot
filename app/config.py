import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN .env faylida topilmadi!")

# ======================= VIP VA LIMIT SOZLAMALARI =======================

# Karta raqami kodda emas, Render'dagi Environment Variable'da turadi
CARD_NUMBER = os.getenv("CARD_NUMBER", "")

VIP_PRICE = 14900          # so'm
VIP_HOURS = 24             # VIP muddati (soat)

FREE_LIMIT = 3             # bepul foydalanuvchi uchun video soni
LIMIT_WAIT_SECONDS = 3600  # limit tugagach kutish vaqti (1 soat)

# Tungi avto-tasdiqlash oralig'i (Toshkent vaqti): 23:00 dan 07:00 gacha
NIGHT_START_HOUR = 23
NIGHT_END_HOUR = 7

# O'zbekiston vaqti (UTC+5, yozgi/qishki vaqt yo'q)
TASHKENT = timezone(timedelta(hours=5))
