"""Webhook notifications — Discord and Telegram."""
from __future__ import annotations

import httpx


def _post(url: str, payload: dict) -> bool:
    try:
        r = httpx.post(url, json=payload, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def send_discord(webhook_url: str, message: str) -> bool:
    if not webhook_url:
        return False
    return _post(webhook_url, {"content": message})


def send_telegram(token: str, chat_id: str, message: str) -> bool:
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    return _post(url, {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})


def notify(config, message: str) -> None:
    """Send to all configured channels."""
    if config.discord_webhook:
        send_discord(config.discord_webhook, message)
    if config.telegram_token and config.telegram_chat_id:
        send_telegram(config.telegram_token, config.telegram_chat_id, message)
