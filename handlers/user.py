"""
Обработчики пользователей
"""

import asyncio
import re
import logging
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_ID, CHAT_ID, DELAY_SECONDS
from database import (
    save_user, user_has_name, update_user_name, update_user_phone,
    get_content, get_start_messages, update_user_status,
    save_channel_msg_id, get_channel_msg_id
)
from keyboards import phone_keyboard, remove_keyboard
from states import UserFlow

router = Router()
logger = logging.getLogger(__name__)

_pending_tasks: dict[int, asyncio.Task] = {}

# Regex для номера телефона
PHONE_RE = re.compile(r'[\+\s\-\(\)]')


def extract_phone(text: str) -> str | None:
    """Извлекает номер телефона из текста."""
    digits = re.sub(r'\D', '', text)
    # Узбекистан: 998XXXXXXXXX или 9XXXXXXXXX
    if len(digits) == 12 and digits.startswith('998'):
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 11 and digits.startswith('8'):
        return f"+7{digits[1:]}"
    if len(digits) == 11 and digits.startswith('9'):
        return f"+{digits}"
    if len(digits) == 12:
        return f"+{digits}"
    return None


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    user_id  = message.from_user.id
    username = message.from_user.username

    await save_user(user_id, username)

    args  = message.text.split(maxsplit=1)
    param = args[1].strip() if len(args) > 1 else ""

    logger.info(f"[/start] user_id={user_id}, param='{param}'")

    # Уведомление в канал о новом пользователе
    await _notify_channel_start(bot, user_id, username)

    # СЦЕНАРИЙ 2: реферальный
    if param == "video":
        content = await get_content()
        youtube      = content.get("youtube_link", "—")
        welcome_text = content.get("welcome_text", "👋 Посмотрите видео по ссылке ниже:")
        await message.answer(f"{welcome_text}\n\n🎥 {youtube}")
        return

    # СЦЕНАРИЙ 1: обычный
    if await user_has_name(user_id):
        await message.answer("👋 Добро пожаловать снова! Вы уже зарегистрированы.")
        return

    # Отправляем стартовые сообщения
    await _send_start_messages(bot, user_id)

    # Отменяем предыдущий таймер
    if user_id in _pending_tasks:
        _pending_tasks[user_id].cancel()

    task = asyncio.create_task(_delayed_ask_name(bot, user_id, state))
    _pending_tasks[user_id] = task


async def _send_start_messages(bot: Bot, user_id: int):
    """Отправляет все стартовые сообщения пользователю через copyMessage."""
    msgs = await get_start_messages()
    if not msgs:
        logger.info(f"[start_msgs] Нет стартовых сообщений для user_id={user_id}")
        return

    for msg in msgs:
        try:
            message_ids = msg.get("message_ids", [msg["message_id"]])

            if len(message_ids) > 1:
                # Медиагруппа — пересылаем все сообщения разом через forward_messages
                await bot.forward_messages(
                    chat_id=user_id,
                    from_chat_id=msg["chat_id"],
                    message_ids=message_ids
                )
            else:
                # Одиночное сообщение — копируем без пометки "переслано"
                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=msg["chat_id"],
                    message_id=msg["message_id"]
                )
        except Exception as e:
            logger.error(f"[start_msgs] Ошибка pos={msg['position']} для {user_id}: {e}")
            # Fallback — копируем по одному
            try:
                for mid in msg.get("message_ids", [msg["message_id"]]):
                    await bot.copy_message(
                        chat_id=user_id,
                        from_chat_id=msg["chat_id"],
                        message_id=mid
                    )
            except Exception as e2:
                logger.error(f"[start_msgs] Fallback ошибка: {e2}")


async def _notify_channel_start(bot: Bot, user_id: int, username: str | None):
    """Отправляет уведомление в канал что пользователь нажал /start."""
    uname = f"@{username}" if username else "—"
    text = (
        f"👤 <b>Новый пользователь нажал старт</b>\n\n"
        f"Username: {uname}\n"
        f"User ID: <code>{user_id}</code>"
    )
    try:
        msg = await bot.send_message(CHAT_ID, text, parse_mode="HTML")
        await save_channel_msg_id(user_id, msg.message_id)
    except Exception as e:
        logger.error(f"[channel] Ошибка уведомления: {e}")
        try:
            await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        except Exception:
            pass


async def _update_channel_registered(bot: Bot, user_id: int, name: str, username: str | None):
    """Обновляет сообщение в канале после регистрации."""
    msg_id = await get_channel_msg_id(user_id)
    if not msg_id:
        return
    uname = f"@{username}" if username else "—"
    text = (
        f"✅ <b>Пользователь зарегистрирован</b>\n\n"
        f"Имя: {name}\n"
        f"Username: {uname}\n"
        f"User ID: <code>{user_id}</code>"
    )
    try:
        await bot.edit_message_text(text, chat_id=CHAT_ID, message_id=msg_id, parse_mode="HTML")
    except Exception as e:
        logger.error(f"[channel] Ошибка обновления сообщения: {e}")


async def _delayed_ask_name(bot: Bot, user_id: int, state: FSMContext):
    try:
        await asyncio.sleep(DELAY_SECONDS)
        if await user_has_name(user_id):
            return
        await bot.send_message(user_id, "✏️ Введите ваше имя:")
        await state.set_state(UserFlow.waiting_name)
        logger.info(f"[timer] Запросили имя у user_id={user_id}")
    except asyncio.CancelledError:
        logger.info(f"[timer] Задача отменена для user_id={user_id}")
    except Exception as e:
        logger.error(f"[timer] Ошибка для user_id={user_id}: {e}")
    finally:
        _pending_tasks.pop(user_id, None)


# ---------------------------------------------------------------------------
# Ввод имени
# ---------------------------------------------------------------------------

@router.message(UserFlow.waiting_name, F.text)
async def handle_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if message.text.startswith("/"):
        await message.answer("⚠️ Пожалуйста, введите ваше имя.")
        return
    await update_user_name(message.from_user.id, name)
    await state.set_state(UserFlow.waiting_phone)
    await message.answer(
        "📱 Отправьте ваш номер телефона:",
        reply_markup=phone_keyboard()
    )


# ---------------------------------------------------------------------------
# Получение телефона — через кнопку
# ---------------------------------------------------------------------------

@router.message(UserFlow.waiting_phone, F.contact)
async def handle_contact(message: Message, state: FSMContext, bot: Bot):
    await _process_phone(message, state, bot, message.contact.phone_number)


# ---------------------------------------------------------------------------
# Получение телефона — текстом
# ---------------------------------------------------------------------------

@router.message(UserFlow.waiting_phone, F.text)
async def handle_phone_text(message: Message, state: FSMContext, bot: Bot):
    phone = extract_phone(message.text)
    if not phone:
        await message.answer(
            "⚠️ Не могу распознать номер телефона.\n\n"
            "Попробуйте в формате: +998901234567\n"
            "Или нажмите кнопку 📱"
        )
        return
    await _process_phone(message, state, bot, phone)


async def _process_phone(message: Message, state: FSMContext, bot: Bot, phone: str):
    """Общая логика обработки телефона."""
    user_id  = message.from_user.id
    username = message.from_user.username

    await update_user_phone(user_id, phone)
    await update_user_status(user_id, "registered")
    await state.clear()

    await message.answer("✅ Спасибо! Ваши данные приняты.", reply_markup=remove_keyboard())

    # Получаем имя
    from database import aiosqlite, DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            name = row[0] if row else "—"

    # Обновляем сообщение в канале
    await _update_channel_registered(bot, user_id, name, username)

    # Отправляем заявку в канал
    uname = f"@{username}" if username else "—"
    text = (
        f"📋 <b>Новая заявка:</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📞 Телефон: {phone}\n"
        f"🔗 Username: {uname}\n"
        f"🆔 ID: {user_id}"
    )
    try:
        await bot.send_message(CHAT_ID, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось отправить заявку: {e}")
        try:
            await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Досрочный ввод текста (пока идёт таймер)
# ---------------------------------------------------------------------------

@router.message(F.text & ~F.text.startswith("/"))
async def handle_free_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    current_state = await state.get_state()

    if current_state == UserFlow.waiting_name:
        await handle_name(message, state)
        return

    if user_id in _pending_tasks:
        _pending_tasks[user_id].cancel()
        _pending_tasks.pop(user_id, None)

        if await user_has_name(user_id):
            await message.answer("✅ Вы уже зарегистрированы.")
            return

        await message.answer("✏️ Введите ваше имя:")
        await state.set_state(UserFlow.waiting_name)
