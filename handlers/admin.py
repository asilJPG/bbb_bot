"""
Обработчики администратора
"""

import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN_ID, ADMIN_IDS, CHAT_ID
from database import (
    update_content, get_all_user_ids, get_start_messages,
    add_start_message, clear_start_messages, get_unregistered_users, get_stats
)
from keyboards import (
    admin_main_keyboard, start_msgs_keyboard, msg_added_keyboard,
    confirm_clear_keyboard, youtube_submenu_keyboard
)
from states import AdminFlow

router = Router()
logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------------------------------------------------------------------------
# /admin
# ---------------------------------------------------------------------------

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    await state.clear()
    await message.answer("🔐 <b>Панель администратора</b>", parse_mode="HTML",
                         reply_markup=admin_main_keyboard())
    
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    await message.answer(f"ID: {message.from_user.id}\nADMIN_IDS: {ADMIN_IDS}\nADMIN_ID: {ADMIN_ID}")

@router.callback_query(F.data == "back_to_main")
async def cb_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔐 <b>Панель администратора</b>", parse_mode="HTML",
                                     reply_markup=admin_main_keyboard())
    await callback.answer()


# ---------------------------------------------------------------------------
# СТАРТОВЫЕ СООБЩЕНИЯ
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_start_msgs")
async def cb_start_msgs(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.clear()
    msgs = await get_start_messages()
    count = len(msgs)
    await callback.message.edit_text(
        f"⚙️ <b>Стартовые сообщения</b>\n\n"
        f"Сейчас в цепочке: <b>{count}</b> сообщений\n\n"
        f"Они отправляются пользователю при нажатии /start",
        parse_mode="HTML",
        reply_markup=start_msgs_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "msg_add")
async def cb_msg_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.answer(
        "📎 Отправьте сообщение для START цепочки.\n\n"
        "Это может быть:\n"
        "• Текст\n"
        "• Фото\n"
        "• Видео\n"
        "• Фото или видео с подписью\n\n"
        "Сообщение будет скопировано и отправлено пользователям именно в таком виде."
    )
    await state.set_state(AdminFlow.adding_msg)
    await callback.answer()


# Храним таймеры для сборки медиагрупп
_media_group_timers: dict[str, asyncio.Task] = {}


@router.message(AdminFlow.adding_msg)
async def handle_add_msg(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    media_group_id = message.media_group_id

    if media_group_id:
        # Сохраняем каждое сообщение из альбома
        await add_start_message(message.chat.id, message.message_id, media_group_id)

        # Отменяем предыдущий таймер для этой группы
        if media_group_id in _media_group_timers:
            _media_group_timers[media_group_id].cancel()

        # Ждём 1 секунду — если новых сообщений не будет, считаем группу завершённой
        async def finish_group():
            await asyncio.sleep(1)
            msgs = await get_start_messages()
            grp = next((m for m in msgs if m.get("media_group_id") == media_group_id), None)
            position = grp["position"] if grp else "?"
            await state.clear()
            try:
                await bot.send_message(
                    message.chat.id,
                    f"✅ <b>Альбом добавлен!</b>\n"
                    f"Файлов в альбоме: <b>{len(grp['message_ids']) if grp else '?'}</b>\n"
                    f"Позиция в цепочке: <b>{position}</b>",
                    parse_mode="HTML",
                    reply_markup=msg_added_keyboard()
                )
            except Exception:
                pass
            _media_group_timers.pop(media_group_id, None)

        task = asyncio.create_task(finish_group())
        _media_group_timers[media_group_id] = task
    else:
        # Обычное сообщение (не альбом)
        position = await add_start_message(message.chat.id, message.message_id)
        await state.clear()
        await message.answer(
            f"✅ <b>Сообщение добавлено!</b>\n"
            f"Позиция в цепочке: <b>{position}</b>",
            parse_mode="HTML",
            reply_markup=msg_added_keyboard()
        )
        logger.info(f"[admin] Добавлено стартовое сообщение pos={position}")


@router.callback_query(F.data == "msg_preview")
async def cb_msg_preview(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    msgs = await get_start_messages()
    if not msgs:
        await callback.message.answer("📭 Стартовых сообщений нет.")
        await callback.answer()
        return
    await callback.message.answer(f"📋 Показываю {len(msgs)} сообщений:")
    for msg in msgs:
        try:
            await bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=msg["chat_id"],
                message_id=msg["message_id"]
            )
        except Exception as e:
            await callback.message.answer(f"⚠️ Сообщение #{msg['position']} недоступно: {e}")
    await callback.answer()


@router.callback_query(F.data == "msg_simulate")
async def cb_msg_simulate(callback: CallbackQuery, bot: Bot):
    """Предпросмотр — симуляция /start для админа."""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    msgs = await get_start_messages()
    if not msgs:
        await callback.message.answer("📭 Стартовых сообщений нет. Добавьте хотя бы одно.")
        await callback.answer()
        return
    await callback.message.answer("👀 <b>Предпросмотр /start:</b>", parse_mode="HTML")
    for msg in msgs:
        try:
            await bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=msg["chat_id"],
                message_id=msg["message_id"]
            )
        except Exception as e:
            await callback.message.answer(f"⚠️ Ошибка: {e}")
    await callback.message.answer("— конец цепочки —", reply_markup=start_msgs_keyboard())
    await callback.answer()


@router.callback_query(F.data == "msg_clear")
async def cb_msg_clear(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.edit_text(
        "⚠️ <b>Вы уверены?</b>\n\nВсе стартовые сообщения будут удалены.",
        parse_mode="HTML",
        reply_markup=confirm_clear_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "msg_clear_confirm")
async def cb_msg_clear_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await clear_start_messages()
    await callback.message.edit_text(
        "🗑 <b>Все стартовые сообщения удалены.</b>",
        parse_mode="HTML",
        reply_markup=start_msgs_keyboard()
    )
    await callback.answer()
    logger.info("[admin] Стартовые сообщения очищены.")


# ---------------------------------------------------------------------------
# СТАТИСТИКА
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_stats")
async def cb_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    stats = await get_stats()
    total     = stats["total"]
    with_name = stats["with_name"]
    with_phone = stats["with_phone"]
    registered = stats["registered"]

    pct = lambda x: f"{round(x/total*100)}%" if total > 0 else "0%"

    await callback.message.edit_text(
        f"📊 <b>Статистика воронки</b>\n\n"
        f"👥 Нажали /start:       <b>{total}</b>\n"
        f"✏️ Ввели имя:           <b>{with_name}</b> ({pct(with_name)})\n"
        f"📞 Оставили телефон:    <b>{with_phone}</b> ({pct(with_phone)})\n"
        f"✅ Зарегистрированы:    <b>{registered}</b> ({pct(registered)})",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="menu_stats")],
            [InlineKeyboardButton(text="◀️ Назад",    callback_data="back_to_main")],
        ])
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# НЕЗАРЕГИСТРИРОВАННЫЕ ПОЛЬЗОВАТЕЛИ
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_unreg")
async def cb_unreg(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    users = await get_unregistered_users()
    if not users:
        await callback.message.edit_text(
            "✅ Все пользователи зарегистрированы.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ])
        )
        await callback.answer()
        return

    lines = [f"👤 <b>Незарегистрированные ({len(users)})</b>\n"]
    for u in users[:30]:  # максимум 30 в одном сообщении
        uname = f"@{u['username']}" if u['username'] else "—"
        lines.append(f"• {uname} | ID: <code>{u['user_id']}</code>")

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
        ])
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# НАПИСАТЬ ПОЛЬЗОВАТЕЛЮ
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_write_user")
async def cb_write_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.answer("✉️ Введите <b>User ID</b> пользователя:", parse_mode="HTML")
    await state.set_state(AdminFlow.write_to_user)
    await callback.answer()


@router.message(AdminFlow.write_to_user, F.text)
async def handle_write_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("⚠️ Введите числовой ID пользователя.")
        return
    await state.update_data(target_user_id=int(message.text.strip()))
    await state.set_state(AdminFlow.write_to_user_msg)
    await message.answer("📝 Отправьте сообщение для пользователя:")


@router.message(AdminFlow.write_to_user_msg)
async def handle_write_user_msg(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    data = await state.get_data()
    target_id = data.get("target_user_id")
    await state.clear()
    try:
        await bot.copy_message(target_id, message.chat.id, message.message_id)
        await message.answer(f"✅ Сообщение отправлено пользователю <code>{target_id}</code>", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")


# ---------------------------------------------------------------------------
# YOUTUBE
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "menu_youtube")
async def cb_youtube_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.edit_text(
        "🔗 <b>YouTube</b> — выберите что изменить:",
        parse_mode="HTML",
        reply_markup=youtube_submenu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.in_({"edit_youtube", "edit_welcome"}))
async def cb_edit_content(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    prompts = {
        "edit_youtube": ("youtube_link", "Введите новую <b>YouTube-ссылку</b>:"),
        "edit_welcome": ("welcome_text", "Введите новый текст <b>приветственного сообщения</b>:"),
    }
    field, prompt = prompts[callback.data]
    await callback.message.answer(prompt, parse_mode="HTML")
    state_map = {"edit_youtube": AdminFlow.edit_youtube, "edit_welcome": AdminFlow.edit_welcome}
    await state.set_state(state_map[callback.data])
    await state.update_data(edit_field=field)
    await callback.answer()


@router.message(AdminFlow.edit_youtube, F.text)
@router.message(AdminFlow.edit_welcome, F.text)
async def handle_content_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if message.text.startswith("/"):
        await message.answer("⚠️ Сейчас ожидается текст.")
        return
    data  = await state.get_data()
    field = data.get("edit_field")
    if not field:
        await state.clear()
        return
    await update_content(field, message.text.strip())
    await state.clear()
    await message.answer("✅ <b>Сохранено!</b>", parse_mode="HTML", reply_markup=youtube_submenu_keyboard())


# ---------------------------------------------------------------------------
# РАССЫЛКА
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "broadcast")
async def cb_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.answer("📢 Отправьте сообщение для рассылки (текст, фото или видео):")
    await state.set_state(AdminFlow.broadcast)
    await callback.answer()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("📢 Отправьте сообщение для рассылки:")
    await state.set_state(AdminFlow.broadcast)


@router.message(AdminFlow.broadcast)
async def handle_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    user_ids = await get_all_user_ids()
    success, failed = 0, 0
    await message.answer(f"⏳ Рассылка для {len(user_ids)} пользователей...")
    for uid in user_ids:
        try:
            await bot.copy_message(uid, message.chat.id, message.message_id)
            success += 1
        except Exception as e:
            logger.warning(f"[broadcast] {uid}: {e}")
            failed += 1
    await message.answer(f"✅ Готово! Доставлено: {success}, ошибок: {failed}")


# ---------------------------------------------------------------------------
# ДОП. КОМАНДЫ
# ---------------------------------------------------------------------------

@router.message(Command("cleardb"))
async def cmd_cleardb(message: Message):
    if not is_admin(message.from_user.id):
        return
    import aiosqlite
    from database import DB_PATH
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users")
        await db.commit()
    await message.answer("✅ База пользователей очищена.")


@router.message(Command("getlink"))
async def cmd_getlink(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    info = await bot.get_me()
    link = f"https://t.me/{info.username}?start=video"
    await message.answer(f"🔗 <b>Реферальная ссылка:</b>\n\n<code>{link}</code>", parse_mode="HTML")


# Импорт для статистики
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
