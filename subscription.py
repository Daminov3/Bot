from app.database import get_all_channels


async def get_unsubscribed_channels(bot, user_id):

    channels = get_all_channels()

    # Kanal bo'lmasa
    if not channels:
        return []

    unsubscribed = []

    for channel in channels:

        try:
            member = await bot.get_chat_member(
                chat_id=channel,
                user_id=user_id
            )

            if member.status not in [
                "member",
                "administrator",
                "creator"
            ]:
                unsubscribed.append(channel)

        except Exception:
            # Agar bot kanalni tekshira olmasa
            unsubscribed.append(channel)

    return unsubscribed



async def check_subscription(bot, user_id):

    unsubscribed = await get_unsubscribed_channels(
        bot,
        user_id
    )

    return len(unsubscribed) == 0