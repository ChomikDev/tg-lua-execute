import telebot
from flask import Flask, request
from lupa import LuaRuntime
import os
import json
import re

API_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = f"/{API_TOKEN}"
WEBHOOK_URL = f"https://tg-lua-execute.onrender.com{WEBHOOK_PATH}"

EAA_DATA_FILE = "eaa_counter.json"

# Загрузка счётчиков эаа
if os.path.exists(EAA_DATA_FILE):
    with open(EAA_DATA_FILE, "r") as f:
        eaa_counter = json.load(f)
else:
    eaa_counter = {}

def save_eaa_data():
    with open(EAA_DATA_FILE, "w") as f:
        json.dump(eaa_counter, f)

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = str(message.from_user.id)
    text = message.text.lower()

    if message.chat.type != 'private':
        # Только для групп
        if "дайте скрипт" in text:
            bot.reply_to(message, "game:Shutdown()")
        elif re.match(r"^эаа$", text, re.IGNORECASE):
            username = message.from_user.username or f"id{message.from_user.id}"
            eaa_counter[username] = eaa_counter.get(username, 0) + 1
            save_eaa_data()
            bot.reply_to(message, f"накопил эаа +1")
        elif text == "топ эаа":
            top = sorted(eaa_counter.items(), key=lambda x: x[1], reverse=True)[:10]
            lines = [f"{i+1}. @{user} - {count}" for i, (user, count) in enumerate(top)]
            reply = "*Эаа*\n" + "\n".join(lines)
            bot.reply_to(message, reply, parse_mode="Markdown")

    # execute работает везде
    if text.startswith("execute"):
        execute_lua(message)

def execute_lua(message):
    code = message.text[len("execute"):].strip()
    output = []

    def py_print(*args):
        output.append(" ".join(str(arg) for arg in args))

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals()["print"] = py_print

    try:
        lua.execute(code)
        result = "\n".join(output)
        escaped_result = escape_markdown(result)
        escaped_code = escape_markdown(code)

        if result:
            msg = f"*Callback:*\n`{escaped_result}`\n*Your Code:*\n```lua\n{escaped_code}\n```"
        else:
            msg = f"*Successfully runned!*\n```lua\n{escaped_code}\n```"
    except Exception as e:
        escaped_error = str(e).replace('`', "'")
        escaped_code = escape_markdown(code)
        msg = f"*Callback:*\n`{escaped_error}`\n*Your Code:*\n```lua\n{escaped_code}\n```"

    bot.reply_to(message, msg, parse_mode="MarkdownV2", reply_to_message_id=message.message_id)

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return 'Bot is running (Webhook mode)'

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
