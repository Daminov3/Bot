import logging
from datetime import datetime, timezone

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import (
    ADMIN_ID,
    CARD_NUMBER,
    VIP_PRICE,
    VIP_HOURS,
    NIGHT_START_HOUR,
    NIGHT_END_HOUR,
    TASHKENT,
)
from app.database import (
    create_payment,
    update_payment_status,
    has_recent_auto_approval,
    grant_vip,
    revoke_vip,
    get_vip_until,
)
from app.states.movie_state import VipState

router = Router()


# ----------------------- yordamchi funksiyalar -----------------------

def _fmt_dt(dt):
    """Vaqtni Toshkent vaqtida ko'rsatadi"""
    return dt.astimezone(TASHKENT).strftime("%d.%m.%Y %H:%M")


def _price_text():
    return f"{VIP_PRICE:,}".replace(",", " ")


def _is_night():
    """Toshkent vaqti bilan 23:00 dan 07:00 gacha"""
    hour = datetime.now(TASHKENT).hour
    return hour >= NIGHT_START_HOUR or hour < NIGHT_END_HOUR


def _review_keyboard(payment_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"vipok:{payment_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"vipno:{payment_id}"),
    ]])


def _revoke_keyboard(payment_id):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🚫 VIP ni bekor qilish", callback_data=f"viprev:{payment_id}"),
    ]])


async def _mark_message(callback: types.CallbackQuery, text: str):
    """Admin xabaridagi tugmalarni olib tashlab, natijani yozib qo'yadi"""
    caption = (callback.message.caption or "") + f"\n\n{text}"
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=None)
    except Exception:
        pass


# ----------------------- foydalanuvchi tomoni -----------------------

@router.callback_query(F.data == "vip_buy")
async def vip_buy(callback: types.CallbackQuery, state: FSMContext):
    if not CARD_NUMBER:
        await callback.answer("VIP hozircha mavjud emas.", show_alert=True)
        return

    text = ""

    until = get_vip_until(callback.from_user.id)
    if until and until > datetime.now(timezone.utc):
        text += (
            f"✅ Sizda VIP faol: {_fmt_dt(until)} gacha.\n"
            "Yana to'lov qilsangiz, muddat uzayadi.\n\n"
        )

    text += (
        "💎 <b>VIP foydalanish</b>\n\n"
        "♾ Kinolar cheklovsiz\n"
        f"💰 Narxi: <b>{_price_text()} so'm</b>\n\n"
        f"💳 Karta raqami:\n<code>{CARD_NUMBER}</code>\n\n"
        "Pulni o'tkazing va <b>chek rasmini</b> shu yerga yuboring."
    )

    await callback.message.answer(text, parse_mode="HTML")
    await state.set_state(VipState.waiting_check)
    await callback.answer()


@router.message(VipState.waiting_check, lambda m: bool(m.photo))
async def receive_check(message: types.Message, state: FSMContext):
    user = message.from_user
    file_id = message.photo[-1].file_id

    # Tunda (23:00-07:00) va bu tunda hali avto-tasdiq olmagan bo'lsa: avtomatik
    auto = _is_night() and not has_recent_auto_approval(user.id)

    await state.clear()

    if auto:
        payment_id = create_payment(user.id, file_id, "auto_approved", auto=True)
        until = grant_vip(user.id, VIP_HOURS)

        await message.answer(
            "✅ To'lov qabul qilindi!\n\n"
            f"💎 VIP faol: {_fmt_dt(until)} gacha.\n"
            "🎬 Endi kinolarni cheklovsiz olishingiz mumkin."
        )

        extra = (
            "\n\n🌙 Tunda AVTO-TASDIQLANGAN.\n"
            "Pul kartangizga tushganini tekshiring. Tushmagan bo'lsa, VIP ni bekor qiling."
        )
        keyboard = _revoke_keyboard(payment_id)
    else:
        payment_id = create_payment(user.id, file_id, "pending")

        await message.answer(
            "✅ Chek qabul qilindi.\n\n"
            "Admin tasdiqlagach VIP faollashadi va sizga xabar keladi."
        )

        extra = ""
        keyboard = _review_keyboard(payment_id)

    username = f"@{user.username}" if user.username else "—"
    caption = (
        "💎 VIP to'lov cheki\n\n"
        f"👤 {user.full_name}\n"
        f"🆔 {user.id}\n"
        f"🔗 {username}\n"
        f"💰 {_price_text()} so'm\n"
        f"🕒 {_fmt_dt(datetime.now(timezone.utc))}\n"
        f"#{payment_id}"
        f"{extra}"
    )

    try:
        await message.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=file_id,
            caption=caption,
            reply_markup=keyboard
        )
    except Exception:
        logging.exception("Chekni adminga yuborib bo'lmadi")


def _not_photo_or_command(m: types.Message) -> bool:
    text = m.text or ""
    return not m.photo and not text.startswith("/") and not text.isdigit()


@router.message(VipState.waiting_check, _not_photo_or_command)
async def check_not_photo(message: types.Message):
    await message.answer("📷 Iltimos, to'lov chekining RASMINI yuboring.")


# ----------------------- admin tomoni (tugmalar) -----------------------

@router.callback_query(F.data.startswith("vipok:"))
async def vip_approve(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    payment_id = int(callback.data.split(":")[1])
    user_id = update_payment_status(payment_id, "approved", ["pending"])

    if user_id is None:
        await callback.answer("Bu chek allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    until = grant_vip(user_id, VIP_HOURS)

    try:
        await callback.bot.send_message(
            user_id,
            "✅ To'lov tasdiqlandi!\n\n"
            f"💎 VIP faol: {_fmt_dt(until)} gacha.\n"
            "🎬 Endi kinolarni cheklovsiz olishingiz mumkin."
        )
    except Exception:
        pass

    await _mark_message(callback, "✅ Tasdiqlandi")
    await callback.answer("Tasdiqlandi")


@router.callback_query(F.data.startswith("vipno:"))
async def vip_reject(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    payment_id = int(callback.data.split(":")[1])
    user_id = update_payment_status(payment_id, "rejected", ["pending"])

    if user_id is None:
        await callback.answer("Bu chek allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    try:
        await callback.bot.send_message(
            user_id,
            "❌ To'lov tasdiqlanmadi.\n\n"
            "Agar to'lov qilgan bo'lsangiz, \"💎 VIP foydalanish\" tugmasi orqali "
            "chekni qaytadan yuboring."
        )
    except Exception:
        pass

    await _mark_message(callback, "❌ Rad etildi")
    await callback.answer("Rad etildi")


@router.callback_query(F.data.startswith("viprev:"))
async def vip_revoke(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    payment_id = int(callback.data.split(":")[1])
    user_id = update_payment_status(payment_id, "revoked", ["auto_approved"])

    if user_id is None:
        await callback.answer("Bu chek allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    revoke_vip(user_id, VIP_HOURS)

    try:
        await callback.bot.send_message(
            user_id,
            "🚫 VIP bekor qilindi: to'lov topilmadi.\n\n"
            "Agar xato bo'lsa, chekni qaytadan yuboring."
        )
    except Exception:
        pass

    await _mark_message(callback, "🚫 VIP bekor qilindi")
    await callback.answer("VIP bekor qilindi")
