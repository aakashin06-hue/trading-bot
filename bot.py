"""
bot.py
The live Telegram bot: command menu, inline buttons, market reports with
RSI-backed bias, position calculator, and a trade journal.
"""

from flask import Flask, request
import telebot
from telebot import types
from helpers import (
    build_market_report, calculate_position, LOT_SIZES,
    add_trade, get_trades, close_trade, get_journal_stats
)

# ============ FILL THIS IN ============
BOT_TOKEN = "8772965274:AAH-oULagaBtC1lEkojRslTqkD18ifjTY6c"
# =======================================

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)

user_data = {}

bot.set_my_commands([
    types.BotCommand("start", "Open the main menu"),
    types.BotCommand("market", "Get calendar, news, prices & bias"),
    types.BotCommand("calculate", "Position size & stop loss calculator"),
    types.BotCommand("history", "View your trade journal"),
    types.BotCommand("help", "How to use this bot"),
])


def main_menu_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📊  Market Update", callback_data="market"),
        types.InlineKeyboardButton("🧮  Position Calculator", callback_data="calculate"),
        types.InlineKeyboardButton("📝  Trade Journal", callback_data="history"),
        types.InlineKeyboardButton("ℹ️  Help", callback_data="help"),
    )
    return kb


def instrument_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🥇 Gold", callback_data="calc_GOLD"),
        types.InlineKeyboardButton("🥈 Silver", callback_data="calc_SILVER"),
        types.InlineKeyboardButton("₿ Bitcoin", callback_data="calc_BITCOIN"),
        types.InlineKeyboardButton("Ξ Ethereum", callback_data="calc_ETHEREUM"),
    )
    return kb


HELP_TEXT = (
    "<b>🤖 Market Bot — Help</b>\n\n"
    "📊 <b>Market Update</b> — this week's high-impact events, latest news, "
    "live prices, and a trend + RSI bias for Gold, Silver, Bitcoin & Ethereum.\n\n"
    "🧮 <b>Position Calculator</b> — enter your account balance, risk %, entry "
    "and stop loss price, and get your position size and lot size.\n\n"
    "📝 <b>Trade Journal</b> — save calculator results as trades, then mark "
    "them Win or Loss later to track your stats.\n\n"
    "⚠️ <i>This bot provides data and calculations only — not financial advice.</i>"
)


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Welcome to your Market Bot</b>\n\nChoose an option below, or type / to see all commands.",
        reply_markup=main_menu_keyboard()
    )


@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.send_message(message.chat.id, HELP_TEXT, reply_markup=main_menu_keyboard())


@bot.message_handler(commands=["market"])
def market(message):
    send_market_report(message.chat.id)


@bot.message_handler(commands=["calculate"])
def calculate_start(message):
    bot.send_message(message.chat.id, "Pick an instrument:", reply_markup=instrument_keyboard())


@bot.message_handler(commands=["history"])
def history(message):
    send_journal(message.chat.id)


def send_market_report(chat_id):
    msg = bot.send_message(chat_id, "⏳ Fetching latest data...")
    report = build_market_report()
    bot.edit_message_text(report, chat_id, msg.message_id, reply_markup=main_menu_keyboard())


def send_journal(chat_id):
    trades = get_trades(chat_id, limit=8)
    stats = get_journal_stats(chat_id)

    text = (
        f"📝 <b>Trade Journal</b>\n\n"
        f"⏳ Open: <b>{stats['open']}</b>   ✅ Wins: <b>{stats['wins']}</b>   "
        f"❌ Losses: <b>{stats['losses']}</b>   🎯 Win rate: <b>{stats['win_rate']}%</b>\n\n"
    )

    if not trades:
        text += "No trades saved yet. Use /calculate — every result is saved here automatically."
        bot.send_message(chat_id, text, reply_markup=main_menu_keyboard())
        return

    for t in trades:
        status_icon = {"open": "⏳", "win": "✅", "loss": "❌"}[t["status"]]
        text += (f"{status_icon} #{t['id']} <b>{t['instrument']}</b> {t['direction']} — "
                  f"{t['entry']} → {t['stop']}, {t['lot_size']} lots\n")

    kb = types.InlineKeyboardMarkup(row_width=1)
    open_trades = [t for t in trades if t["status"] == "open"]
    if open_trades:
        kb.add(types.InlineKeyboardButton("🔧 Close a Trade", callback_data="close_menu"))
    kb.add(types.InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu"))

    bot.send_message(chat_id, text, reply_markup=kb)


def send_close_menu(chat_id):
    trades = get_trades(chat_id, limit=8)
    open_trades = [t for t in trades if t["status"] == "open"]

    if not open_trades:
        bot.send_message(chat_id, "No open trades to close.", reply_markup=main_menu_keyboard())
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for t in open_trades:
        kb.add(types.InlineKeyboardButton(
            f"#{t['id']} {t['instrument']} {t['direction']} @ {t['entry']}",
            callback_data=f"pick_{t['id']}"
        ))
    kb.add(types.InlineKeyboardButton("⬅️ Back", callback_data="history"))

    bot.send_message(chat_id, "Which trade do you want to close?", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    if call.data == "market":
        bot.delete_message(chat_id, call.message.message_id)
        send_market_report(chat_id)

    elif call.data == "help":
        bot.edit_message_text(HELP_TEXT, chat_id, call.message.message_id, reply_markup=main_menu_keyboard())

    elif call.data == "calculate":
        bot.edit_message_text("Pick an instrument:", chat_id, call.message.message_id,
                               reply_markup=instrument_keyboard())

    elif call.data == "menu":
        bot.edit_message_text(
            "👋 <b>Welcome to your Market Bot</b>\n\nChoose an option below, or type / to see all commands.",
            chat_id, call.message.message_id, reply_markup=main_menu_keyboard()
        )

    elif call.data == "history":
        bot.delete_message(chat_id, call.message.message_id)
        send_journal(chat_id)

    elif call.data == "close_menu":
        bot.delete_message(chat_id, call.message.message_id)
        send_close_menu(chat_id)

    elif call.data.startswith("pick_"):
        trade_id = int(call.data.replace("pick_", ""))
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ Win", callback_data=f"win_{trade_id}"),
            types.InlineKeyboardButton("❌ Loss", callback_data=f"loss_{trade_id}"),
        )
        bot.edit_message_text(f"Mark trade #{trade_id} as:", chat_id, call.message.message_id, reply_markup=kb)

    elif call.data.startswith("calc_"):
        instrument = call.data.replace("calc_", "")
        user_data[chat_id] = {"instrument": instrument}
        bot.send_message(chat_id, f"Selected <b>{instrument}</b>.\n\nWhat is your account balance (USD)?")
        bot.register_next_step_handler(call.message, calc_balance)

    elif call.data.startswith("win_") or call.data.startswith("loss_"):
        outcome, trade_id = call.data.split("_")
        outcome = "win" if outcome == "win" else "loss"
        close_trade(chat_id, int(trade_id), outcome)
        bot.delete_message(chat_id, call.message.message_id)
        send_journal(chat_id)


def calc_balance(message):
    chat_id = message.chat.id
    try:
        user_data[chat_id]["balance"] = float(message.text.strip())
    except (ValueError, KeyError):
        bot.send_message(chat_id, "Please enter a number. Send /calculate to try again.")
        return
    bot.send_message(chat_id, "What % of your account do you want to risk on this trade? (e.g. 1 for 1%)")
    bot.register_next_step_handler(message, calc_risk)


def calc_risk(message):
    chat_id = message.chat.id
    try:
        user_data[chat_id]["risk"] = float(message.text.strip())
    except (ValueError, KeyError):
        bot.send_message(chat_id, "Please enter a number. Send /calculate to try again.")
        return
    bot.send_message(chat_id, "What is your entry price?")
    bot.register_next_step_handler(message, calc_entry)


def calc_entry(message):
    chat_id = message.chat.id
    try:
        user_data[chat_id]["entry"] = float(message.text.strip())
    except (ValueError, KeyError):
        bot.send_message(chat_id, "Please enter a number. Send /calculate to try again.")
        return
    bot.send_message(chat_id, "What is your stop loss price?")
    bot.register_next_step_handler(message, calc_stop)


def calc_stop(message):
    chat_id = message.chat.id
    try:
        stop_price = float(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "Please enter a number. Send /calculate to try again.")
        return

    data = user_data.get(chat_id)
    if not data:
        bot.send_message(chat_id, "Session expired. Send /calculate to try again.")
        return

    result = calculate_position(data["balance"], data["risk"], data["entry"], stop_price, data["instrument"])

    if result is None:
        bot.send_message(chat_id, "Entry and stop loss can't be the same price. Send /calculate to try again.")
        return

    trade_id = add_trade(
        chat_id, data["instrument"], data["entry"], stop_price,
        result["lot_size"], result["risk_amount"], result["direction"]
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📝 View in Journal", callback_data="history"))

    bot.send_message(
        chat_id,
        f"📊 <b>Position Sizing Result</b>\n\n"
        f"Instrument: <b>{data['instrument']}</b>\n"
        f"Direction: <b>{result['direction']}</b>\n"
        f"Risk amount: <b>${result['risk_amount']}</b>\n"
        f"Position size: <b>{result['units']} units</b>\n"
        f"Lot size: <b>{result['lot_size']} lots</b>\n\n"
        f"✅ Automatically saved to your journal as #{trade_id}.\n\n"
        f"⚠️ <i>This is a math calculation based on your inputs only, not financial advice.</i>",
        reply_markup=kb
    )
    user_data.pop(chat_id, None)


@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("UTF-8")
        update = types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print("WEBHOOK ERROR:", repr(e))
    return "OK", 200


@app.route("/", methods=["GET"])
def index():
    return "Bot is running.", 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
