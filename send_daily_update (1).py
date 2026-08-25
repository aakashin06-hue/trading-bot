"""
send_daily_update.py
Run this on a schedule (e.g. once a day) to automatically PUSH the market
report to your Telegram chat, without you having to type /market yourself.
"""

import requests
from helpers import build_market_report

# ============ FILL THESE IN ============
BOT_TOKEN = "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE"
CHAT_ID = "PASTE_YOUR_CHAT_ID_HERE"
# ========================================

report = build_market_report()

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
requests.post(url, data={
    "chat_id": CHAT_ID,
    "text": report,
    "parse_mode": "Markdown"
})
