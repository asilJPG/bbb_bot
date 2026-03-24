import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID  = int(os.environ.get("ADMIN_ID", "0"))
CHAT_ID   = int(os.environ.get("CHAT_ID", "0"))

_ids = os.environ.get("ADMIN_IDS", "")
ADMIN_IDS = set(
    int(i.strip()) for i in _ids.split(",") if i.strip().isdigit()
)
if ADMIN_ID:
    ADMIN_IDS.add(ADMIN_ID)

DELAY_SECONDS = 300
