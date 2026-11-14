from aiogram.fsm.state import StatesGroup, State


class MovieState(StatesGroup):
    waiting_code = State()
    waiting_title = State()
    waiting_video = State()

    # Backup import
    waiting_backup = State()

    # Maxfiy kanal qo'shish
    waiting_private_forward = State()
    waiting_private_link = State()


class VipState(StatesGroup):
    # VIP to'lov chekini kutish
    waiting_check = State()
