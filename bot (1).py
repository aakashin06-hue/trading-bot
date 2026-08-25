"""
bot.py
The live Telegram bot. Handles /start, /market, and /calculate.
Runs as a Flask web app so PythonAnywhere can keep it reachable for free.
"""

from flask import Flask, request
import telebot
from helpers import build_market_report, calculate_position, LOT_SIZES

# ============ FILL THIS IN ============
BOT_TOKEN = "8772965274:AAH-oULagaBtC1lEkojRslTqkD18ifjTY6c"
# =======================================

bot = telebot.TeleBot(BOT_TOKEN)
bot.parse_mode = None
app = Flask(__name__)

# Temporary storage for the step-by-step /calculate conversation
user_data = {}


@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "👋 Welcome! Commands:\n"
        "/market - Calendar, news, prices & bias for Gold, Silver, BTC, ETH\n"
        "/calculate - Work out your stop loss position size & lot size"
    )


@bot.message_handler(commands=["market"])
def market(message):
    bot.reply_to(message, "Fetching latest data, one moment...")
    report = build_market_report()
    bot.send_message(message.chat.id, report, parse_mode="Markdown")


@bot.message_handler(commands=["calculate"])
def calculate_start(message):
    bot.reply_to(message, "Which instrument? Reply: GOLD, SILVER, BITCOIN, or ETHEREUM")
    bot.register_next_step_handler(message, calc_instrument)


def calc_instrument(message):
    instrument = message.text.strip().upper()
    if instrument not in LOT_SIZES:
        bot.reply_to(message, "Please type one of: GOLD, SILVER, BITCOIN, ETHEREUM. Send /calculate to try again.")
        return
    user_data[message.chat.id] = {"instrument": instrument}
    bot.reply_to(message, "What is your account balance (in USD)?")
    bot.register_next_step_handler(message, calc_balance)


def calc_balance(message):
    try:
        user_data[message.chat.id]["balance"] = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "Please enter a number. Send /calculate to try again.")
        return
    bot.reply_to(message, "What % of your account do you want to risk on this trade? (e.g. 1 for 1%)")
    bot.register_next_step_handler(message, calc_risk)


def calc_risk(message):
    try:
        user_data[message.chat.id]["risk"] = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "Please enter a number. Send /calculate to try again.")
        return
    bot.reply_to(message, "What is your entry price?")
    bot.register_next_step_handler(message, calc_entry)


def calc_entry(message):
    try:
        user_data[message.chat.id]["entry"] = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "Please enter a number. Send /calculate to try again.")
        return
    bot.reply_to(message, "What is your stop loss price?")
    bot.register_next_step_handler(message, calc_stop)


def calc_stop(message):
    try:
        stop_price = float(message.text.strip())
    except ValueError:
        bot.reply_to(message, "Please enter a number. Send /calculate to try again.")
        return

    data = user_data.get(message.chat.id)
    result = calculate_position(data["balance"], data["risk"], data["entry"], stop_price, data["instrument"])

    if result is None:
        bot.reply_to(message, "Entry and stop loss can't be the same price. Send /calculate to try again.")
        return

    bot.reply_to(
        message,
        f"📊 *Position Sizing Result*\n"
        f"Instrument: {data['instrument']}\n"
        f"Risk amount: ${result['risk_amount']}\n"
        f"Position size: {result['units']} units\n"
        f"Lot size: {result['lot_size']} lots\n\n"
        f"⚠️ This is a math calculation based on your inputs only, not financial advice.",
        parse_mode="Markdown"
    )
    user_data.pop(message.chat.id, None)


# ---- Webhook route Telegram will send messages to ----
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    try:
        json_str = request.get_data().decode("UTF-8")
        update = telebot.types.Update.de_json(json_str)
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
