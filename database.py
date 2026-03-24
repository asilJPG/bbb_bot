"""
База данных SQLite
"""

import aiosqlite
import json
import logging

DB_PATH = "bot.db"
logger = logging.getLogger(__name__)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Пользователи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                name          TEXT,
                phone         TEXT,
                status        TEXT DEFAULT 'not_registered',
                channel_msg_id INTEGER,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Стартовые сообщения (новая таблица)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS start_messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                position   INTEGER NOT NULL
            )
        """)

        # Контент (youtube + welcome)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id            INTEGER PRIMARY KEY CHECK (id = 1),
                youtube_link  TEXT DEFAULT 'https://youtube.com',
                welcome_text  TEXT DEFAULT '👋 Посмотрите видео по ссылке ниже:'
            )
        """)

        # Совместимость со старой базой
        for table, col, default in [
            ("users", "status", "'not_registered'"),
            ("users", "channel_msg_id", "NULL"),
            ("content", "youtube_link", "'https://youtube.com'"),
            ("content", "welcome_text", "'👋 Посмотрите видео по ссылке ниже:'"),
        ]:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass

        await db.execute("INSERT OR IGNORE INTO content (id) VALUES (1)")
        await db.commit()
    logger.info("База данных инициализирована.")


# ---------------------------------------------------------------------------
# ПОЛЬЗОВАТЕЛИ
# ---------------------------------------------------------------------------

async def save_user(user_id: int, username: str | None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        await db.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
        await db.commit()


async def user_has_name(user_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])


async def update_user_name(user_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET name = ?, status = 'registered' WHERE user_id = ?",
            (name, user_id)
        )
        await db.commit()


async def update_user_phone(user_id: int, phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET phone = ? WHERE user_id = ?", (phone, user_id))
        await db.commit()


async def update_user_status(user_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
        await db.commit()


async def save_channel_msg_id(user_id: int, msg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET channel_msg_id = ? WHERE user_id = ?", (msg_id, user_id))
        await db.commit()


async def get_channel_msg_id(user_id: int) -> int | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT channel_msg_id FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def get_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cur:
            return [r[0] for r in await cur.fetchall()]


async def get_unregistered_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, username, registered_at FROM users WHERE status = 'not_registered'"
        ) as cur:
            rows = await cur.fetchall()
            return [{"user_id": r[0], "username": r[1], "registered_at": r[2]} for r in rows]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE name IS NOT NULL") as cur:
            with_name = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE phone IS NOT NULL") as cur:
            with_phone = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE status = 'registered'") as cur:
            registered = (await cur.fetchone())[0]
    return {
        "total": total,
        "with_name": with_name,
        "with_phone": with_phone,
        "registered": registered,
    }


# ---------------------------------------------------------------------------
# СТАРТОВЫЕ СООБЩЕНИЯ
# ---------------------------------------------------------------------------

async def add_start_message(chat_id: int, message_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM start_messages") as cur:
            position = (await cur.fetchone())[0]
        await db.execute(
            "INSERT INTO start_messages (chat_id, message_id, position) VALUES (?, ?, ?)",
            (chat_id, message_id, position)
        )
        await db.commit()
        return position


async def get_start_messages() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, chat_id, message_id, position FROM start_messages ORDER BY position"
        ) as cur:
            rows = await cur.fetchall()
            return [{"id": r[0], "chat_id": r[1], "message_id": r[2], "position": r[3]} for r in rows]


async def clear_start_messages():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM start_messages")
        await db.commit()


# ---------------------------------------------------------------------------
# КОНТЕНТ
# ---------------------------------------------------------------------------

async def get_content() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT youtube_link, welcome_text FROM content WHERE id = 1") as cur:
            row = await cur.fetchone()
            if row:
                return {
                    "youtube_link": row[0] or "https://youtube.com",
                    "welcome_text": row[1] or "👋 Посмотрите видео по ссылке ниже:",
                }
    return {}


async def update_content(field: str, value: str):
    allowed = {"youtube_link", "welcome_text"}
    if field not in allowed:
        raise ValueError(f"Недопустимое поле: {field}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE content SET {field} = ? WHERE id = 1", (value,))
        await db.commit()
