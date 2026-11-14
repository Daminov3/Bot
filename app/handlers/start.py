from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from app.database import add_user
from app.handlers.movie import build_subscription_keyboard, vip_keyboard
from app.middlewares.subscription import get_unsubscribed_channels

router = Router()


@router.message(CommandStart())
async def start_command(message: Message):

    add_user(
        message.from_user.id,
        message.from_user.full_name
    )

    unsubscribed = await get_unsubscribed_channels(
        message.bot,
        message.from_user.id
    )

    if unsubscribed:
        # Kanallarga obuna so'raymiz, pastida VIP tugmasi
        await message.answer(
            "Assalomu alaykum!\n\n🎬 Kino botga xush kelibsiz.\n\n"
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:",
            reply_markup=build_subscription_keyboard(unsubscribed, with_vip=True)
        )
    else:
        await message.answer(
            "Assalomu alaykum!\n\n🎬 Kino botga xush kelibsiz.\n\n"
            "Kino kodini yuboring.",
            reply_markup=vip_keyboard()
        )
