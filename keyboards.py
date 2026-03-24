from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard():
    from aiogram.types import ReplyKeyboardRemove
    return ReplyKeyboardRemove()


# ---------------------------------------------------------------------------
# АДМИН — главное меню
# ---------------------------------------------------------------------------

def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Управление стартовыми сообщениями", callback_data="menu_start_msgs")],
        [InlineKeyboardButton(text="🔗 YouTube-ссылка",                    callback_data="menu_youtube")],
        [InlineKeyboardButton(text="📊 Статистика",                        callback_data="menu_stats")],
        [InlineKeyboardButton(text="👤 Незарегистрированные",              callback_data="menu_unreg")],
        [InlineKeyboardButton(text="✉️ Написать пользователю",             callback_data="menu_write_user")],
        [InlineKeyboardButton(text="📢 Рассылка",                          callback_data="broadcast")],
    ])


# ---------------------------------------------------------------------------
# СТАРТОВЫЕ СООБЩЕНИЯ
# ---------------------------------------------------------------------------

def start_msgs_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить сообщение",        callback_data="msg_add")],
        [InlineKeyboardButton(text="📋 Посмотреть все",            callback_data="msg_preview")],
        [InlineKeyboardButton(text="👀 Предпросмотр /start",       callback_data="msg_simulate")],
        [InlineKeyboardButton(text="❌ Очистить все",              callback_data="msg_clear")],
        [InlineKeyboardButton(text="◀️ Назад",                     callback_data="back_to_main")],
    ])


def msg_added_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ещё",  callback_data="msg_add")],
        [InlineKeyboardButton(text="✅ Закончить",     callback_data="menu_start_msgs")],
    ])


def confirm_clear_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить",  callback_data="msg_clear_confirm")],
        [InlineKeyboardButton(text="❌ Нет",          callback_data="menu_start_msgs")],
    ])


# ---------------------------------------------------------------------------
# YOUTUBE
# ---------------------------------------------------------------------------

def youtube_submenu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Изменить ссылку",      callback_data="edit_youtube")],
        [InlineKeyboardButton(text="✏️ Изменить сообщение",   callback_data="edit_welcome")],
        [InlineKeyboardButton(text="◀️ Назад",                callback_data="back_to_main")],
    ])
