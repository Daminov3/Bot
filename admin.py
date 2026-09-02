import os
import asyncio
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Document
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
    get_all_channels,
    get_all_movies_txt,  # Zaxira faylini oluvchi yangi funksiya
    add_movie
)

router = Router()

# 15 daqiqalik taymerni ushlab turish uchun global o'zgaruvchi
backup_task = None

async def send_delayed_backup(bot: types.Bot):
    """Kinolar yuklab bo'lingach 15 daqiqa o'tib ishlaydigan zaxira yuboruvchi"""
    global backup_task
    try:
        # 15 daqiqa kutamiz (15 minut = 900 soniya)
        await asyncio.sleep(900)
        
        # .txt faylni tayyorlaymiz
        file_path = get_all_movies_txt()
        
        # Hujjat ko'rinishida adminga yuboramiz
        document = FSInputFile(file_path)
        await bot.send_document(
            chat_id=ADMIN_ID,
            document=document,
            caption="📅 Oxirgi kino qo'shilganidan 15 daqiqa o'tdi. Eng so'nggi File IDlar zaxira nusxasi tayyor!"
        )
        
        # Server ichidagi vaqtinchalik .txt faylni o'chiramiz
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except asyncio.CancelledError:
        # Agar 15 daqiqa ichida yangi kino qo'shilsa, bu vazifa bekor qilinadi
        pass
    finally:
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
    
    # Yangi 15 daqiqalik taymerni boshlaymiz
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

@router.message(Command("addchannel"))
async def add_channel_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Foydalanish:\n/addchannel @kanal_username")
        return
    username = args[1]
    if not username.startswith("@"):
        await message.answer("❌ Kanal @ bilan boshlanishi kerak")
        return
    add_channel(username)
    await message.answer(f"✅ Kanal qo‘shildi:\n{username}")

@router.message(Command("channels"))
async def channels_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return
    channels = get_all_channels()
    if not channels:
        await message.answer("📢 Hozircha kanal yo‘q")
        return
    text = "📢 Majburiy kanallar:\n\n"
    for i, channel in enumerate(channels, 1):
        text += f"{i}. {channel}\n"
    await message.answer(text)

@router.message(Command("deletechannel"))
async def delete_channel_command(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz!")
        return

    args = message.text.split()
    if len(args) != 2:
        await message.answer("Foydalanish:\n/deletechannel @kanal_username")
        return

    username = args[1]
    result = delete_channel(username)

    if result:
        await message.answer(f"✅ Kanal o‘chirildi:\n{username}")
    else:
        await message.answer("❌ Bunday kanal topilmadi")

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
