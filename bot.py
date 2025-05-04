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

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = str(message.from_user.id)
    text = message.text.lower()

    if message.chat.type != 'private':
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
            reply = "Эаа\n" + "\n".join(lines)
            bot.reply_to(message, reply)
        elif text == "мои эаа":
            username = message.from_user.username or f"id{message.from_user.id}"
            count = eaa_counter.get(username, 0)
            bot.reply_to(message, f"У тебя {count} эаа")

    if text.startswith("execute"):
        execute_lua(message)
    elif text.startswith("ai "):
        prompt = message.text[3:].strip()
        ai_reply(message, prompt)

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
        if result:
            msg = f"Callback:\n{result}\n\nYour Code:\n{code}"
        else:
            msg = f"Successfully runned!\n\nYour Code:\n{code}"
    except Exception as e:
        msg = f"Callback:\n{str(e)}\n\nYour Code:\n{code}"

    bot.reply_to(message, msg)

def ai_reply(message, prompt):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://t.me/your_bot_username",
        "X-Title": "LuaHelperBot"
    }

    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "Ты помощник реверсер, который пишет скрипты, обходы, помогает с кодом и всегда говорит Эаа в начале сообщений."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        result = response.json()
        reply_text = result["choices"][0]["message"]["content"]
        bot.reply_to(message, reply_text)
    except Exception as e:
        bot.reply_to(message, f"Ошибка AI: {str(e)}")

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
