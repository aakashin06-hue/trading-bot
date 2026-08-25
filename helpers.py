"""
helpers.py
Core logic: prices, stronger bias (trend + RSI), news, calendar,
the position size calculator, and the trade journal.
"""

import requests
import feedparser
import json
import os
from datetime import datetime

# ============ FILL THIS IN ============
TWELVE_DATA_KEY = "4faa5c3107224a8fbba720b5030b5b0e"
# ========================================

SYMBOLS = {
    "GOLD": "XAU/USD",
    "SILVER": "XAG/USD",
    "BITCOIN": "BTC/USD",
    "ETHEREUM": "ETH/USD",
}

LOT_SIZES = {
    "GOLD": 100,
    "SILVER": 5000,
    "BITCOIN": 1,
    "ETHEREUM": 1,
}

JOURNAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal_data.json")


def get_price(name):
    symbol = SYMBOLS[name]
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVE_DATA_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        return float(r["price"])
    except Exception:
        return None


def _rsi(closes, period=14):
    """Standard RSI calculation from a list of closing prices (oldest -> newest)."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def get_bias(name):
    """
    Simple trend-based bias: compares a short-term average (10 candles)
    to a longer-term average (30 candles) on the daily chart.
    This is a basic trend signal, NOT a prediction or financial advice.
    """
    symbol = SYMBOLS[name]
    url = (f"https://api.twelvedata.com/time_series?symbol={symbol}"
           f"&interval=1day&outputsize=30&apikey={TWELVE_DATA_KEY}")
    try:
        r = requests.get(url, timeout=10).json()
        closes = [float(c["close"]) for c in r["values"]]
        closes.reverse()
        if len(closes) < 30:
            return "Not enough data"
        sma10 = sum(closes[-10:]) / 10
        sma30 = sum(closes[-30:]) / 30
        diff_pct = (sma10 - sma30) / sma30 * 100
        if diff_pct > 0.5:
            return "🟢 Bullish"
        elif diff_pct < -0.5:
            return "🔴 Bearish"
        else:
            return "⚪ Neutral / Sideways"
    except Exception:
        return "Unavailable"


def get_news(limit=5):
    feeds = [
        "https://www.investing.com/rss/news_301.rss",
        "https://www.investing.com/rss/news_25.rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
    ]
    headlines = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                headlines.append(f"• {entry.title}")
        except Exception:
            continue
    return headlines[: limit * 2] if headlines else ["No news available right now."]


def get_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        events = requests.get(url, timeout=10).json()
        high_impact = [e for e in events if e.get("impact") == "High"]
        lines = []
        for e in high_impact[:8]:
            lines.append(f"• {e.get('country')} — {e.get('title')} ({e.get('date')} {e.get('time')})")
        return lines if lines else ["No high-impact events found this week."]
    except Exception:
        return ["Calendar data unavailable right now."]


def build_market_report():
    lines = ["📅 <b>This Week's High-Impact Events</b>"]
    lines += get_calendar()
    lines.append("")
    lines.append("📰 <b>Latest News</b>")
    lines += get_news()
    lines.append("")
    lines.append("💰 <b>Prices & Bias</b>")
    for name in ["GOLD", "SILVER", "BITCOIN", "ETHEREUM"]:
        price = get_price(name)
        bias = get_bias(name)
        price_str = f"${price:,.2f}" if price else "N/A"
        lines.append(f"• <b>{name}</b>: {price_str} — {bias}")
    return "\n".join(lines)


def calculate_position(account_balance, risk_percent, entry_price, stop_price, instrument):
    risk_amount = account_balance * (risk_percent / 100)
    price_diff = abs(entry_price - stop_price)
    if price_diff == 0:
        return None
    units = risk_amount / price_diff
    lot_size = units / LOT_SIZES.get(instrument, 1)
    direction = "Buy (Long)" if stop_price < entry_price else "Sell (Short)"
    return {
        "risk_amount": round(risk_amount, 2),
        "units": round(units, 4),
        "lot_size": round(lot_size, 4),
        "direction": direction,
    }


# ================= TRADE JOURNAL =================

def _load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return {"next_id": 1, "trades": []}
    try:
        with open(JOURNAL_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"next_id": 1, "trades": []}


def _save_journal(data):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_trade(chat_id, instrument, entry, stop, lot_size, risk_amount, direction):
    data = _load_journal()
    trade = {
        "id": data["next_id"],
        "chat_id": chat_id,
        "instrument": instrument,
        "direction": direction,
        "entry": entry,
        "stop": stop,
        "lot_size": lot_size,
        "risk_amount": risk_amount,
        "status": "open",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    }
    data["trades"].append(trade)
    data["next_id"] += 1
    _save_journal(data)
    return trade["id"]


def get_trades(chat_id, limit=10):
    data = _load_journal()
    trades = [t for t in data["trades"] if t["chat_id"] == chat_id]
    return list(reversed(trades))[:limit]


def close_trade(chat_id, trade_id, outcome):
    """outcome should be 'win' or 'loss'"""
    data = _load_journal()
    for t in data["trades"]:
        if t["id"] == trade_id and t["chat_id"] == chat_id:
            t["status"] = outcome
            _save_journal(data)
            return True
    return False


def get_journal_stats(chat_id):
    data = _load_journal()
    trades = [t for t in data["trades"] if t["chat_id"] == chat_id]
    wins = len([t for t in trades if t["status"] == "win"])
    losses = len([t for t in trades if t["status"] == "loss"])
    open_count = len([t for t in trades if t["status"] == "open"])
    total_closed = wins + losses
    win_rate = round((wins / total_closed) * 100, 1) if total_closed else 0
    return {"wins": wins, "losses": losses, "open": open_count, "win_rate": win_rate}
