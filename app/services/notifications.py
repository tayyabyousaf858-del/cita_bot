"""
Notification service.
Subscribes to Redis pub/sub and dispatches:
- Telegram bot messages
- Firebase Cloud Messaging (optional)
"""
import asyncio
import json
import os
import structlog
import httpx
from typing import Optional

logger = structlog.get_logger()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID  = int(os.environ.get("ADMIN_TELEGRAM_ID", "0"))
BACKEND_URL        = os.environ.get("BACKEND_URL", "http://backend:8000")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_telegram(chat_id: int, text: str, photo_path: Optional[str] = None):
    """Send a Telegram message (with optional photo)."""
    async with httpx.AsyncClient(timeout=15) as client:
        if photo_path and os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                await client.post(
                    f"{TELEGRAM_API}/sendPhoto",
                    data={"chat_id": chat_id, "caption": text, "parse_mode": "HTML"},
                    files={"photo": f},
                )
        else:
            await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )


async def get_user_telegram_id(user_id: int) -> Optional[int]:
    """Fetch telegram_id for a user from backend."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get(f"{BACKEND_URL}/api/users/{user_id}/telegram_id")
            return res.json().get("telegram_id")
    except Exception:
        return None


async def handle_appointment_found(data: dict):
    """Notify user and admin when appointment slot is found."""
    job_id  = data.get("job_id")
    user_id = data.get("user_id")
    screenshot = data.get("screenshot_path")

    text = (
        "🎉 <b>¡CITA DISPONIBLE!</b>\n\n"
        f"🔧 Job ID: <b>#{job_id}</b>\n\n"
        "⚡ Accede ahora al sistema ICP para reservar tu cita:\n"
        "👉 https://icp.administracionelectronica.gob.es/icpplus/index.html\n\n"
        "⚠️ <i>La disponibilidad puede cambiar rápidamente.</i>"
    )

    # Notify user
    tg_id = await get_user_telegram_id(user_id)
    if tg_id:
        await send_telegram(tg_id, text, screenshot)

    # Notify admin
    admin_text = text + f"\n\n👤 User ID: {user_id}"
    await send_telegram(ADMIN_TELEGRAM_ID, admin_text, screenshot)

    logger.info("Appointment found notification sent", job_id=job_id, user_id=user_id)


async def handle_otp_required(data: dict):
    """Alert admin immediately when OTP is detected."""
    otp_id     = data.get("otp_id")
    job_id     = data.get("job_id")
    user_id    = data.get("user_id")
    screenshot = data.get("screenshot_path")

    text = (
        "🔐 <b>OTP REQUERIDA</b>\n\n"
        f"👤 Usuario ID: <b>{user_id}</b>\n"
        f"🔧 Job ID: <b>#{job_id}</b>\n"
        f"🆔 OTP ID: <b>#{otp_id}</b>\n\n"
        "⚡ <b>Acción requerida inmediatamente.</b>\n"
        "Accede al dashboard para resolver el OTP."
    )
    await send_telegram(ADMIN_TELEGRAM_ID, text, screenshot)
    logger.warning("OTP required notification sent to admin", otp_id=otp_id, job_id=job_id)


HANDLERS = {
    "appointment_found": handle_appointment_found,
    "otp_required":      handle_otp_required,
}


async def run_notification_service(redis_client):
    """Subscribe to Redis and dispatch notifications."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("notifications:telegram")

    logger.info("Notification service listening")
    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                payload = json.loads(message["data"])
                event_type = payload.get("type")
                data = payload.get("data", {})
                handler = HANDLERS.get(event_type)
                if handler:
                    await handler(data)
            except Exception as e:
                logger.error("Notification handler error", error=str(e))
