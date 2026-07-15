"""
Avisos push via Telegram.

Requereix dues variables d'entorn (les configurem com a Secrets a GitHub,
veure GUIA_PROJECTE):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

Si no estan definides, els avisos simplement no s'envien (no fa fallar el
bot per això) — útil per poder provar el bot abans de tenir Telegram
configurat.
"""

import os
import logging

import requests

from config import TELEGRAM_ENABLED

log = logging.getLogger("telegram_alerts")


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_ENABLED:
        return False

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.info("Telegram no configurat (falten TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) — avís no enviat.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
        if resp.status_code != 200:
            log.warning(f"Telegram ha respost {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception as e:
        # Un avís que falla mai ha de tombar el bot ni bloquejar el rebalanceig
        log.warning(f"No s'ha pogut enviar l'avís de Telegram: {e}")
        return False
