from app.database import get_all_channels_full

JOINED_STATUSES = {"member", "administrator", "creator"}


def _to_chat_id(identifier):
    """'-1001234567890' -> int, '@kanal' -> '@kanal'"""
    value = str(identifier).strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


async def get_unsubscribed_channels(bot, user_id):
    """
    Foydalanuvchi a'zo bo'lmagan kanallarni qaytaradi.
    Har bir element: (identifier, invite_link, title)
    """
    channels = get_all_channels_full()

    # Kanal bo'lmasa
    if not channels:
        return []

    unsubscribed = []

    for identifier, invite_link, title in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=_to_chat_id(identifier),
                user_id=user_id
            )

            status = str(getattr(member.status, "value", member.status))

            joined = status in JOINED_STATUSES or (
                status == "restricted" and getattr(member, "is_member", False)
            )

            if not joined:
                unsubscribed.append((identifier, invite_link, title))

        except Exception:
            # Bot kanalni tekshira olmasa (masalan, kanalda admin bo'lmasa)
            unsubscribed.append((identifier, invite_link, title))

    return unsubscribed


async def check_subscription(bot, user_id):

    unsubscribed = await get_unsubscribed_channels(
        bot,
        user_id
    )

    return len(unsubscribed) == 0
