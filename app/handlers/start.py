from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.database import add_user

router = Router()


@router.message(CommandStart())
async def start_command(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.full_name
    )

    await message.answer(
        "Assalomu alaykum!\n\n🎬 Kino botga xush kelibsiz."
    )