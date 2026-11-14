import math

from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import ADMIN_ID, FREE_LIMIT
from app.database import get_movie, try_consume_download, refund_download, is_vip
from app.middlewares.subscription import (
    check_subscription,
    get_unsubscribed_channels
)

router = Router()


def vip_button_row():
    return [
        InlineKeyboardButton(
            text="💎 VIP foydalanish",
            callback_data="vip_buy"
        )
    ]


def vip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[vip_button_row()])


def build_subscription_keyboard(channels, with_vip=False):
    """channels: [(identifier, invite_link, title), ...]"""
    buttons = []

    for identifier, invite_link, title in channels:
        # Maxfiy kanal: taklif havolasi, ochiq kanal: @username orqali havola
        if invite_link:
            url = invite_link
        elif str(identifier).startswith("@"):
            url = f"https://t.me/{identifier[1:]}"
        else:
            # Maxfiy kanal, lekin havola yo'q: tugma yasab bo'lmaydi
            continue

        name = title or identifier

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📢 {name}",
                    url=url
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

    if with_vip:
        buttons.append(vip_button_row())

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


async def create_subscription_keyboard(bot, user_id, with_vip=False):
    channels = await get_unsubscribed_channels(
        bot,
        user_id
    )

    return build_subscription_keyboard(channels, with_vip=with_vip)


@router.message()
async def send_movie(message: types.Message):
    if not message.text:
        return

    if not message.text.isdigit():
        return

    user_id = message.from_user.id

    subscribed = await check_subscription(
        message.bot,
        user_id
    )

    if not subscribed:
        keyboard = await create_subscription_keyboard(
            message.bot,
            user_id,
            with_vip=True
        )

        await message.answer(
            "❌ Kino olish uchun avval quyidagi kanallarga a'zo bo'ling:",
            reply_markup=keyboard
        )
        return

    movie_code = int(message.text)
    movie = get_movie(movie_code)

    # Mavjud bo'lmagan kod limitdan ayirilmaydi
    if movie is None:
        await message.answer(
            "❌ Bunday kino topilmadi"
        )
        return

    title, file_id = movie

    # LIMIT TEKSHIRUVI (admin va VIP uchun cheklov yo'q)
    if user_id != ADMIN_ID:
        allowed, wait_seconds = try_consume_download(
            user_id,
            message.from_user.full_name
        )

        if not allowed:
            minutes = max(1, math.ceil(wait_seconds / 60))
            await message.answer(
                f"⏳ Bepul limit tugadi ({FREE_LIMIT} ta video).\n\n"
                "💎 VIP tarifga o'ting yoki "
                f"{minutes} daqiqadan keyin qayta urinib ko'ring.",
                reply_markup=vip_keyboard()
            )
            return

    # Videoni kontent himoyasi (protect_content=True) bilan yuboramiz
    try:
        await message.answer_video(
            video=file_id,
            caption=f"🎬 {title}",
            protect_content=True
        )
    except Exception:
        # Video yuborilmasa, hisoblangan videoni qaytaramiz
        if user_id != ADMIN_ID and not is_vip(user_id):
            refund_download(user_id)
        raise


@router.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription_button(callback: types.CallbackQuery):
    subscribed = await check_subscription(
        callback.bot,
        callback.from_user.id
    )

    if subscribed:
        await callback.message.edit_text(
            "✅ A'zolik tasdiqlandi.\n\n"
            "🎬 Endi kino kodini yuboring.",
            reply_markup=vip_keyboard()
        )
    else:
        keyboard = await create_subscription_keyboard(
            callback.bot,
            callback.from_user.id,
            with_vip=True
        )

        try:
            await callback.message.edit_reply_markup(
                reply_markup=keyboard
            )
        except Exception:
            # Tugmalar o'zgarmagan bo'lsa Telegram xato beradi, e'tibor bermaymiz
            pass

        await callback.answer(
            "❌ Hali barcha kanallarga a'zo emassiz!",
            show_alert=True
        )
