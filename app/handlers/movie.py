from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.database import get_movie
from app.middlewares.subscription import (
    check_subscription,
    get_unsubscribed_channels
)

router = Router()

async def create_subscription_keyboard(bot, user_id):
    channels = await get_unsubscribed_channels(
        bot,
        user_id
    )

    buttons = []

    for channel in channels:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📢 {channel}",
                    url=f"https://t.me/{channel.replace('@','')}"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="✅ Tekshirish",
                callback_data="check_subscription"
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )

@router.message()
async def send_movie(message: types.Message):
    if not message.text:
        return

    if not message.text.isdigit():
        return

    subscribed = await check_subscription(
        message.bot,
        message.from_user.id
    )

    if not subscribed:
        keyboard = await create_subscription_keyboard(
            message.bot,
            message.from_user.id
        )

        await message.answer(
            "❌ Kino olish uchun avval quyidagi kanallarga a'zo bo'ling:",
            reply_markup=keyboard
        )
        return

    movie_code = int(message.text)
    movie = get_movie(movie_code)

    if movie is None:
        await message.answer(
            "❌ Bunday kino topilmadi"
        )
        return

    title, file_id = movie

    # Videoni kontent himoyasi (protect_content=True) bilan yuboramiz
    await message.answer_video(
        video=file_id,
        caption=f"🎬 {title}",
        protect_content=True  # <-- Mana shu qator hamma ko'chirish va yuklashlarni bloklaydi!
    )

@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_button(callback: types.CallbackQuery):
    subscribed = await check_subscription(
        callback.bot,
        callback.from_user.id
    )

    if subscribed:
        await callback.message.edit_text(
            "✅ A'zolik tasdiqlandi.\n\n"
            "🎬 Endi kino kodini yuboring."
        )
    else:
        keyboard = await create_subscription_keyboard(
            callback.bot,
            callback.from_user.id
        )

        await callback.message.edit_reply_markup(
            reply_markup=keyboard
        )

        await callback.answer(
            "❌ Hali barcha kanallarga a'zo emassiz!",
            show_alert=True
        )
