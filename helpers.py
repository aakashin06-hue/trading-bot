"""
helpers.py
All the 'brain' functions for the bot: fetching prices, working out bias,
pulling news and calendar events, and doing the stop-loss/position-size math.
"""

import requests
import feedparser

# ============ FILL THESE IN ============
TWELVE_DATA_KEY = "4faa5c3107224a8fbba720b5030b5b0e"
# ========================================

# Symbols as Twelve Data expects them
SYMBOLS = {
    "GOLD": "XAU/USD",
    "SILVER": "XAG/USD",
    "BITCOIN": "BTC/USD",
    "ETHEREUM": "ETH/USD",
}

# Default "lot" sizes used only for the position size calculator.
# These are common broker conventions - adjust if your broker differs.
LOT_SIZES = {
    "GOLD": 100,      # 1 standard lot = 100 oz
    "SILVER": 5000,   # 1 standard lot = 5000 oz
    "BITCOIN": 1,      # 1 lot = 1 BTC
    "ETHEREUM": 1,      # 1 lot = 1 ETH
}


def get_price(name):
    """Get the latest price for GOLD / SILVER / BITCOIN / ETHEREUM."""
    symbol = SYMBOLS[name]
    url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={TWELVE_DATA_KEY}"
    try:
        r = requests.get(url, timeout=10).json()
        return float(r["price"])
    except Exception:
        return None


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
        closes.reverse()  # oldest -> newest
        if len(closes) < 30:
            return "Not enough data"
        sma10 = sum(closes[-10:]) / 10
        sma30 = sum(closes[-30:]) / 30
        diff_pct = (sma10 - sma30) / sma30 * 100
        if diff_pct > 0.5:
            return "Bullish"
        elif diff_pct < -0.5:
            return "Bearish"
        else:
            return "Neutral / Sideways"
    except Exception:
        return "Unavailable"


def get_news(limit=5):
    """Pull latest headlines from free RSS feeds (no API key needed)."""
    feeds = [
        "https://www.investing.com/rss/news_301.rss",   # commodities
        "https://www.investing.com/rss/news_25.rss",    # forex
        "https://www.coindesk.com/arc/outboundfeeds/rss/",  # crypto
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
    """
    Pull this week's high-impact economic events from a free public
    ForexFactory calendar feed (no key needed, unofficial but widely used).
    """
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
    """Assembles the full report: calendar, news, prices, bias."""
    lines = ["📅 *This Week's High-Impact Events*"]
    lines += get_calendar()
    lines.append("")
    lines.append("📰 *Latest News*")
    lines += get_news()
    lines.append("")
    lines.append("💰 *Prices & Bias*")
    for name in ["GOLD", "SILVER", "BITCOIN", "ETHEREUM"]:
        price = get_price(name)
        bias = get_bias(name)
        price_str = f"${price:,.2f}" if price else "N/A"
        lines.append(f"• {name}: {price_str} — Bias: {bias}")
    return "\n".join(lines)


def calculate_position(account_balance, risk_percent, entry_price, stop_price, instrument):
    """
    Returns risk amount, position size (units), and lot size.
    NOT financial advice - purely a math calculation based on your inputs.
    """
    risk_amount = account_balance * (risk_percent / 100)
    price_diff = abs(entry_price - stop_price)
    if price_diff == 0:
        return None
    units = risk_amount / price_diff
    lot_size = units / LOT_SIZES.get(instrument, 1)
    return {
        "risk_amount": round(risk_amount, 2),
        "units": round(units, 4),
        "lot_size": round(lot_size, 4),
    }
