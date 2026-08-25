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


def _timeframe_signal(closes):
    """Returns (score, label, rsi) for one timeframe's closing prices."""
    if len(closes) < 30:
        return None
    sma10 = sum(closes[-10:]) / 10
    sma30 = sum(closes[-30:]) / 30
    trend_up = sma10 > sma30
    rsi = _rsi(closes, 14)

    if rsi is None:
        score = 1 if trend_up else -1
        label = "Bullish" if trend_up else "Bearish"
        return score, label, None

    if trend_up and rsi < 70:
        return 1, "Bullish", rsi
    elif trend_up and rsi >= 70:
        return 0.5, "Bullish (OB)", rsi
    elif not trend_up and rsi > 30:
        return -1, "Bearish", rsi
    elif not trend_up and rsi <= 30:
        return -0.5, "Bearish (OS)", rsi
    else:
        return 0, "Neutral", rsi


def _swing_structure(highs, lows, window=2):
    """
    Detects simple swing-high/swing-low market structure from a daily
    candle series. Compares the last two swing highs and last two swing
    lows to classify as HH+HL (uptrend structure), LH+LL (downtrend
    structure), or Mixed.
    """
    pivot_highs, pivot_lows = [], []
    n = len(highs)
    for i in range(window, n - window):
        if all(highs[i] > highs[i - k] for k in range(1, window + 1)) and \
           all(highs[i] > highs[i + k] for k in range(1, window + 1)):
            pivot_highs.append(highs[i])
        if all(lows[i] < lows[i - k] for k in range(1, window + 1)) and \
           all(lows[i] < lows[i + k] for k in range(1, window + 1)):
            pivot_lows.append(lows[i])

    if len(pivot_highs) < 2 or len(pivot_lows) < 2:
        return None

    higher_high = pivot_highs[-1] > pivot_highs[-2]
    higher_low = pivot_lows[-1] > pivot_lows[-2]

    if higher_high and higher_low:
        return "HH+HL", 1
    elif not higher_high and not higher_low:
        return "LH+LL", -1
    else:
        return "Mixed", 0


def get_bias(name):
    """
    Shows Technical Bias (RSI + trend on 1H/4H/Daily) and Structure Bias
    (swing HH/HL vs LH/LL on 4H/Daily) as two separate readings, so you can
    see whether momentum and price structure agree or disagree. This is a
    basic technical signal, NOT a prediction or financial advice.
    """
    symbol = SYMBOLS[name]
    timeframes = [("1H", "1h"), ("4H", "4h"), ("Daily", "1day")]
    technical_lines = []
    structure_lines = []

    for tf_label, interval in timeframes:
        url = (f"https://api.twelvedata.com/time_series?symbol={symbol}"
               f"&interval={interval}&outputsize=50&apikey={TWELVE_DATA_KEY}")
        try:
            r = requests.get(url, timeout=10).json()
            values = list(reversed(r["values"]))
            closes = [float(c["close"]) for c in values]

            signal = _timeframe_signal(closes)
            if signal is None:
                technical_lines.append(f"{tf_label}: n/a")
            else:
                score, label, rsi = signal
                rsi_str = f" RSI {rsi}" if rsi is not None else ""
                technical_lines.append(f"{tf_label}: {label}{rsi_str}")

            # Structure only on 4H and Daily - 1H swings are too noisy to be reliable
            if tf_label in ("4H", "Daily"):
                highs = [float(c["high"]) for c in values]
                lows = [float(c["low"]) for c in values]
                structure = _swing_structure(highs, lows)
                if structure:
                    struct_label, _ = structure
                    structure_lines.append(f"{tf_label}: {struct_label}")
                else:
                    structure_lines.append(f"{tf_label}: n/a")
        except Exception:
            technical_lines.append(f"{tf_label}: n/a")

    technical_str = " | ".join(technical_lines) if technical_lines else "Unavailable"
    structure_str = " | ".join(structure_lines) if structure_lines else "Unavailable"

    return (f"📈 <i>Technical: {technical_str}</i>\n"
            f"   🏗️ <i>Structure: {structure_str}</i>")


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
    lines.append("💰 <b>Prices & Bias</b> <i>(1H + 4H + Daily combined)</i>")
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
