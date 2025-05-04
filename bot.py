import telebot
from flask import Flask, request
from lupa import LuaRuntime
import os
import json
import re
import requests

API_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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

def call_ai_model(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "mistralai/mixtral-8x7b-instruct",
            "messages": [
                {"role": "system", "content": "Ты помощник, который пишет Lua-скрипты и может немного материться, но не оскорбляет участников чата."},
                {"role": "user", "content": prompt}
            ]
        }

        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Ошибка AI: {e}"

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = str(message.from_user.id)
    text = message.text

    if message.text.lower() == "/start":
        bot.reply_to(message,
            "Этат бот был сделан по приколу\n\n"
            "execute (code) — вызывает луа скрипт\n\n"
            "А эта работает только в группах:\n"
            "эаа — вызывает эаа\n"
            "топ эаа — топ 10 эаашников"
        )
        return

    if message.chat.type != 'private':
        # Только для групп
        lowered = text.lower()
        if "дайте скрипт" in lowered:
            bot.reply_to(message, "game:Shutdown()")
        elif lowered == "эаа":
            username = message.from_user.username or f"id{message.from_user.id}"
            eaa_counter[username] = eaa_counter.get(username, 0) + 1
            save_eaa_data()
            bot.reply_to(message, "накопил эаа +1")
        elif lowered == "топ эаа":
            top = sorted(eaa_counter.items(), key=lambda x: x[1], reverse=True)[:10]
            lines = [f"{i+1}. @{user} - {count}" for i, (user, count) in enumerate(top)]
            reply = "*Эаа*\n" + "\n".join(lines)
            bot.reply_to(message, reply, parse_mode="Markdown")

    if text.startswith("execute"):
        execute_lua(message)
    elif text.startswith("ai "):
        prompt = message.text[3:].strip()
        response = call_ai_model(prompt)
        escaped_response = escape_markdown(response)
        bot.reply_to(message, f"*AI:*\n```{escaped_response}```", parse_mode="MarkdownV2")

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
        escaped_error = escape_markdown(str(e))
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
