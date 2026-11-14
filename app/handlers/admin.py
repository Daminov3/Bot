import os
import asyncio
from aiogram import Bot, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, MessageOriginChannel
import re

from app.states.movie_state import MovieState
from app.config import ADMIN_ID

from app.database import (
    get_all_movies,
    delete_movie,
    get_users_count,
    get_movies_count,
    add_channel,
    delete_channel,
    get_all_channels_full,
    get_all_movies_txt,  # Zaxira faylini oluvchi funksiya
    add_movie
)

router = Router()

# 15 daqiqalik taymerni ushlab turish uchun global o'zgaruvchi
backup_task = None


async def send_delayed_backup(bot: Bot):
    """Oxirgi kino yuklangandan 10 daqiqa o'tib ishlaydigan zaxira yuboruvchi"""
    global backup_task
    try:
        # 10 daqiqa kutamiz (10 minut = 600 soniya)
        await asyncio.sleep(600)

        # .txt faylni tayyorlaymiz
        file_path = get_all_movies_txt()

        # Hujjat ko'rinishida adminga yuboramiz
        document = FSInputFile(file_path)
        await bot.send_document(
            chat_id=ADMIN_ID,
            document=document,
            caption="📅 Oxirgi kino qo'shilganidan 10 daqiqa o'tdi. Eng so'nggi File IDlar zaxira nusxasi tayyor!"
        )

        # Server ichidagi vaqtinchalik .txt faylni o'chiramiz
        if os.path.exists(file_path):
            os.remove(file_path)

    except asyncio.CancelledError:
        # Agar 10 daqiqa ichida yangi kino qo'shilsa, bu vazifa bekor qilinadi
        pass
    finally:
        # MUHIM: faqat o'zi hozirgi taymer bo'lsa tozalaymiz.
        # Aks holda bekor qilingan eski taymer yangisini "yo'q qilib" yuboradi
        # va har bir kino uchun alohida backup ketaveradi.
        if backup_task is asyncio.current_task():
            backup_task = None


@router.message(Command("stop"))
async def stop_command(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    await state.clear()
    await message.answer("⛔ Amal bekor qilindi.")


@router.message(Command("import"))
async def import_movies_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return

    await message.answer("📄 backup_movies.txt faylini yuboring.")
    await state.set_state(MovieState.waiting_backup)


@router.message(Command("addmovie"))
async def add_movie_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("Kino kodini yuboring:")
    await state.set_state(MovieState.waiting_code)


@router.message(MovieState.waiting_code)
async def get_movie_code(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer("⛔ Amal bekor qilindi.")
        return
    await state.update_data(movie_code=message.text)
    await message.answer("Kino nomini yuboring:")
    await state.set_state(MovieState.waiting_title)


@router.message(MovieState.waiting_title)
async def get_movie_title(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer("⛔ Amal bekor qilindi.")
        return
    await state.update_data(title=message.text)
    await message.answer("Videoni yuboring:")
    await state.set_state(MovieState.waiting_video)


@router.message(MovieState.waiting_video)
async def get_movie_video(message: types.Message, state: FSMContext):
    global backup_task

    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer("⛔ Amal bekor qilindi.")
        return

    if not message.video:
        await message.answer("Iltimos video yuboring!")
        return

    data = await state.get_data()
    movie_code = data["movie_code"]
    title = data["title"]
    file_id = message.video.file_id

    try:
        movie_code = int(movie_code)
    except ValueError:
        await message.answer("❌ Kino kodi faqat raqam bo‘lishi kerak!")
        await state.clear()
        return

    # Kinoni bazaga saqlaymiz
    add_movie(movie_code, title, file_id)
    await message.answer("✅ Kino saqlandi!")
    await state.clear()

    # AQLLI TAYMER TIZIMI (DEBOUNCE)
    # Agar oldingi kinodan qolgan taymer hali ishlayotgan bo'lsa, uni o'chiramiz
    if backup_task is not None:
        backup_task.cancel()

    # Yangi 10 daqiqalik taymerni boshlaymiz
    backup_task = asyncio.create_task(send_delayed_backup(message.bot))


@router.message(Command("movies"))
async def movies_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    movies = get_all_movies()
    if not movies:
        await message.answer("🎬 Hozircha kino yo‘q")
        return
    text = "🎬 Kinolar:\n\n"
    for movie in movies:
        text += f"{movie[0]} - {movie[1]}\n"
    await message.answer(text)


@router.message(Command("deletemovie"))
async def delete_movie_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Foydalanish:\n/deletemovie 101")
        return
    try:
        movie_code = int(args[1])
    except ValueError:
        await message.answer("❌ Kino kodi son bo‘lishi kerak!")
        return
    result = delete_movie(movie_code)
    if result:
        await message.answer(f"✅ {movie_code} kodli kino o‘chirildi")
    else:
        await message.answer("❌ Bunday kino topilmadi")


@router.message(Command("stats"))
async def stats_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    users = get_users_count()
    movies = get_movies_count()
    text = (
        "📊 Bot statistikasi\n\n"
        f"👤 Foydalanuvchilar: {users} ta\n"
        f"🎬 Kinolar: {movies} ta"
    )
    await message.answer(text)


# ======================= KANALLAR =======================

async def _bot_is_admin(bot: Bot, chat_id) -> bool:
    """Bot kanalda admin ekanini tekshiradi (a'zolikni tekshirish uchun shart)"""
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        status = str(getattr(member.status, "value", member.status))
        return status in ("administrator", "creator")
    except Exception:
        return False


@router.message(Command("addchannel"))
async def add_channel_command(message: types.Message):
    """Ochiq kanal: /addchannel @kanal_username"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer(
            "Foydalanish:\n"
            "/addchannel @kanal_username  — ochiq kanal\n"
            "/addprivate  — maxfiy kanal (havola orqali)"
        )
        return
    username = args[1]
    if not username.startswith("@"):
        await message.answer("❌ Kanal @ bilan boshlanishi kerak")
        return

    title = None
    try:
        chat = await message.bot.get_chat(username)
        title = chat.title
    except Exception:
        pass

    add_channel(username, None, title)

    text = f"✅ Kanal qo‘shildi:\n{username}"
    if not await _bot_is_admin(message.bot, username):
        text += (
            "\n\n⚠️ Bot bu kanalda admin emas. "
            "A'zolikni tekshirish uchun botni kanalga admin qiling."
        )
    await message.answer(text)


async def _save_private_channel(message: types.Message, chat_id: int, link: str) -> bool:
    """Maxfiy kanalni tekshirib, bazaga saqlaydi"""
    bot = message.bot

    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title
    except Exception:
        await message.answer(
            "❌ Kanal topilmadi yoki bot kanalda yo‘q.\n"
            "Botni kanalga admin qilib qo‘shing va qaytadan urinib ko‘ring."
        )
        return False

    if not await _bot_is_admin(bot, chat_id):
        await message.answer(
            "❌ Bot bu kanalda admin emas.\n"
            "Botni kanalga admin qiling va qaytadan urinib ko‘ring."
        )
        return False

    add_channel(str(chat_id), link, title)
    await message.answer(
        f"✅ Maxfiy kanal qo‘shildi:\n"
        f"📢 {title}\n"
        f"🆔 {chat_id}"
    )
    return True


@router.message(Command("addprivate"))
async def add_private_command(message: types.Message, state: FSMContext):
    """
    Maxfiy kanal:
      /addprivate                      -> kanaldan post forward qilish orqali
      /addprivate -1001234567890 https://t.me/+AbCdEf  -> ID va havola bilan
    """
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return

    args = message.text.split()

    if len(args) == 1:
        await message.answer(
            "🔒 Maxfiy kanal qo‘shish\n\n"
            "1) Botni kanalga ADMIN qilib qo‘shing.\n"
            "2) Kanaldan istalgan postni shu yerga forward qiling.\n\n"
            "Forward qilib bo‘lmasa (kanalda himoya yoqilgan bo‘lsa), shunday yuboring:\n"
            "/addprivate -1001234567890 https://t.me/+AbCdEf\n\n"
            "Bekor qilish: /stop"
        )
        await state.set_state(MovieState.waiting_private_forward)
        return

    if len(args) != 3:
        await message.answer(
            "Foydalanish:\n/addprivate -1001234567890 https://t.me/+AbCdEf"
        )
        return

    chat_id_text, link = args[1], args[2]

    if not chat_id_text.lstrip("-").isdigit():
        await message.answer("❌ Kanal ID si raqam bo‘lishi kerak (masalan -1001234567890)")
        return

    if not link.startswith("https://t.me/"):
        await message.answer("❌ Havola https://t.me/ bilan boshlanishi kerak")
        return

    await _save_private_channel(message, int(chat_id_text), link)


@router.message(MovieState.waiting_private_forward)
async def private_channel_forward(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer("⛔ Amal bekor qilindi.")
        return

    origin = message.forward_origin

    if not isinstance(origin, MessageOriginChannel):
        await message.answer(
            "❌ Bu kanaldan forward qilingan post emas.\n"
            "Kanaldan postni forward qiling yoki /stop bosing."
        )
        return

    await state.update_data(chat_id=origin.chat.id)
    await message.answer(
        f"✅ Kanal topildi: {origin.chat.title}\n\n"
        "Endi kanalning taklif havolasini yuboring\n"
        "(masalan: https://t.me/+AbCdEf)"
    )
    await state.set_state(MovieState.waiting_private_link)


@router.message(MovieState.waiting_private_link)
async def private_channel_link(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        await message.answer("⛔ Amal bekor qilindi.")
        return

    link = (message.text or "").strip()

    if not link.startswith("https://t.me/"):
        await message.answer("❌ Havola https://t.me/ bilan boshlanishi kerak. Qaytadan yuboring:")
        return

    data = await state.get_data()
    await state.clear()

    await _save_private_channel(message, data["chat_id"], link)


@router.message(Command("channels"))
async def channels_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    channels = get_all_channels_full()
    if not channels:
        await message.answer("📢 Hozircha kanal yo‘q")
        return
    text = "📢 Majburiy kanallar:\n\n"
    for i, (identifier, invite_link, title) in enumerate(channels, 1):
        if str(identifier).startswith("@"):
            text += f"{i}. {identifier}\n"
        else:
            text += f"{i}. 🔒 {title or 'Maxfiy kanal'}\n   ID: {identifier}\n"
    text += "\nO‘chirish: /deletechannel @username yoki /deletechannel -100..."
    await message.answer(text)


@router.message(Command("deletechannel"))
async def delete_channel_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer(
            "Foydalanish:\n"
            "/deletechannel @kanal_username\n"
            "/deletechannel -1001234567890"
        )
        return

    identifier = args[1]
    result = delete_channel(identifier)

    if result:
        await message.answer(f"✅ Kanal o‘chirildi:\n{identifier}")
    else:
        await message.answer("❌ Bunday kanal topilmadi")


# ======================= BACKUP IMPORT =======================

@router.message(MovieState.waiting_backup)
async def import_backup(message: types.Message, state: FSMContext):

    if not message.document:
        await message.answer("📄 backup_movies.txt faylini yuboring.")
        return

    file = await message.bot.get_file(message.document.file_id)

    file_path = "backup_movies.txt"

    await message.bot.download(file, destination=file_path)

    await message.answer("📥 Fayl qabul qilindi. Import boshlanmoqda...")

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    pattern = r"Kino Kodi:\s*(\d+)\s*\|\s*Nomi:\s*(.*?)\s*\|\s*File ID:\s*(.+)"

    movies = re.findall(pattern, text)

    count = 0

    for movie_code, title, file_id in movies:
        add_movie(
            int(movie_code),
            title.strip(),
            file_id.strip()
        )
        count += 1

    os.remove(file_path)

    await state.clear()

    await message.answer(f"✅ {count} ta kino bazaga import qilindi.")
