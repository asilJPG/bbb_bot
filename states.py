from aiogram.fsm.state import State, StatesGroup


class UserFlow(StatesGroup):
    waiting_name  = State()
    waiting_phone = State()


class AdminFlow(StatesGroup):
    broadcast         = State()
    edit_youtube      = State()
    edit_welcome      = State()
    adding_msg        = State()   # Добавление стартового сообщения
    confirm_clear     = State()   # Подтверждение очистки
    write_to_user     = State()   # Написать пользователю — ввод ID
    write_to_user_msg = State()   # Написать пользователю — ввод сообщения
