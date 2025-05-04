import telebot
from flask import Flask, request
from lupa import LuaRuntime
import os
import json
import re
import time
import requests

API_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = f"/{API_TOKEN}"
WEBHOOK_URL = f"https://tg-lua-execute.onrender.com{WEBHOOK_PATH}"

EAA_DATA_FILE = "eaa_counter.json"
USER_CONTEXT_FILE = "user_context.json"
last_command_time = {}

if os.path.exists(EAA_DATA_FILE):
    with open(EAA_DATA_FILE, "r") as f:
        eaa_counter = json.load(f)
else:
    eaa_counter = {}

if os.path.exists(USER_CONTEXT_FILE):
    with open(USER_CONTEXT_FILE, "r") as f:
        user_context = json.load(f)
else:
    user_context = {}

def save_eaa_data():
    with open(EAA_DATA_FILE, "w") as f:
        json.dump(eaa_counter, f)

def save_user_context():
    with open(USER_CONTEXT_FILE, "w") as f:
        json.dump(user_context, f)

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def is_spamming(user_id):
    now = time.time()
    if user_id in last_command_time:
        if now - last_command_time[user_id] < 2:
            return True
    last_command_time[user_id] = now
    return False

@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(message,
        "Эаа! Этот бот был сделан по приколу.\n\n"
        "**Команды:**\n"
        "- `execute [код]` — вызывает Lua скрипт\n"
        "- `ai [вопрос]` — вызывает AI-помощника\n\n"
        "*Работает только в группах:*\n"
        "- `эаа` — вызывает эаа\n"
        "- `топ эаа` — топ 10 эаашников\n"
        "- `/моиэаа` — сколько ты накопил эаа",
        parse_mode="Markdown")

@bot.message_handler(commands=["моиэаа"])
def my_eaa(message):
    username = message.from_user.username or f"id{message.from_user.id}"
    count = eaa_counter.get(username, 0)
    bot.reply_to(message, f"Ты накопил {count} эаа")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = str(message.from_user.id)
    text = message.text.strip()

    if is_spamming(user_id):
        bot.reply_to(message, "Эаа! Нельзя так часто.", reply_to_message_id=message.message_id)
        return

    if message.chat.type != 'private':
        if "дайте скрипт" in text.lower():
            bot.reply_to(message, "game:Shutdown()")
        elif re.match(r"^эаа$", text, re.IGNORECASE):
            username = message.from_user.username or f"id{message.from_user.id}"
            eaa_counter[username] = eaa_counter.get(username, 0) + 1
            save_eaa_data()
            bot.reply_to(message, "накопил эаа +1")
        elif text.lower() == "топ эаа":
            top = sorted(eaa_counter.items(), key=lambda x: x[1], reverse=True)[:10]
            lines = [f"{i+1}. @{user} — {count}" for i, (user, count) in enumerate(top)]
            reply = "*Эаа*\n" + "\n".join(lines)
            bot.reply_to(message, reply, parse_mode="Markdown")

    if text.lower().startswith("execute"):
        execute_lua(message)
    elif text.lower().startswith("ai"):
        prompt = text[2:].strip()
        handle_ai(message, prompt)

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
            msg = f"*Callback:*\n`{escaped_result}`\n\n*Your Code:*\n```lua\n{escaped_code}\n```"
        else:
            msg = f"*Successfully runned!*\n```lua\n{escaped_code}\n```"
    except Exception as e:
        escaped_error = str(e).replace('`', "'")
        escaped_code = escape_markdown(code)
        msg = f"*Callback:*\n`{escaped_error}`\n\n*Your Code:*\n```lua\n{escaped_code}\n```"

    bot.reply_to(message, msg, parse_mode="MarkdownV2", reply_to_message_id=message.message_id)

def handle_ai(message, prompt):
    user_id = str(message.from_user.id)

    # Инициализация памяти (context) для каждого пользователя
    if user_id not in user_context:
        user_context[user_id] = []

    # Добавляем пользовательский запрос в память
    user_context[user_id].append({"role": "user", "content": prompt})

    # Ограничение на количество сообщений в памяти (например, последние 10)
    if len(user_context[user_id]) > 10:
        user_context[user_id] = user_context[user_id][-10:]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yourdomain.com",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-3.5-turbo",  # Используем ChatGPT 3.5 Turbo
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты помощник реверсер в роблоксе, помогаешь писать скрипты, эксплойты, бекдоры, обходы на C++ так и на луа как полный эксперт. "
                    "Знает все про эксплойты в роблоксе методы обхода как хакер."
                )
            }
        ] + user_context[user_id]
    }

    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        response = r.json()

        # Прямо выводим содержимое ответа без проверки на 'choices'
        reply = response.get("choices", [{}])[0].get("message", {}).get("content", "Ошибка: Не удалось получить ответ от AI.")
        bot.reply_to(message, reply)

        # Добавляем ответ AI в память
        user_context[user_id].append({"role": "assistant", "content": reply})
        save_user_context()  # Сохраняем контекст

    except Exception as e:
        bot.reply_to(message, f"Ошибка AI: {e}")
        print(f"Exception during AI request: {e}")  # Логируем исключение

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
