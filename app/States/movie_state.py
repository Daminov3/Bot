from aiogram.fsm.state import StatesGroup, State


class MovieState(StatesGroup):
    waiting_code = State()
    waiting_title = State()
    waiting_video = State()

    # Backup import
    waiting_backup = State()
