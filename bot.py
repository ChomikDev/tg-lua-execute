import telebot
from flask import Flask, request
from lupa import LuaRuntime
import re
import os
import json
import time
import random

API_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = f"/{API_TOKEN}"
WEBHOOK_URL = f"https://tg-lua-execute.onrender.com{WEBHOOK_PATH}"

EAA_DATA_FILE = "eaa_counter.json"
user_message_times = {}

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

def lua_obfuscate(code):
    bytes_seq = [str(ord(c)) for c in code]
    return f'loadstring("\\{chr(92).join(bytes_seq)}")()'

def lua_deobfuscate(code):
    try:
        match = re.search(r'loadstring\("((?:\\\d{1,3})+)"\)', code)
        if not match:
            return "Invalid obfuscated format."
        byte_seq = match.group(1).split('\\')[1:]
        return ''.join(chr(int(b)) for b in byte_seq)
    except Exception as e:
        return f"Deobfuscation error: {e}"

@bot.message_handler(func=lambda message: message.chat.type != 'private')
def handle_all(message):
    user_id = str(message.from_user.id)
    text = message.text.lower()

    # антиспам
    now = time.time()
    if user_id not in user_message_times:
        user_message_times[user_id] = []
    user_message_times[user_id].append(now)
    user_message_times[user_id] = [t for t in user_message_times[user_id] if now - t < 3]

    if len(user_message_times[user_id]) >= 3:
        bot.reply_to(message, "завали ебало")
        user_message_times[user_id] = []
        return

    if "дайте скрипт" in text:
        bot.reply_to(message, "game:Shutdown()")
    elif re.match(r"^эаа$", text, re.IGNORECASE):  # Проверка на точное "эаа" или "Эаа"
        username = message.from_user.username or f"id{message.from_user.id}"
        eaa_counter[username] = eaa_counter.get(username, 0) + 1
        save_eaa_data()
        bot.reply_to(message, f"накопил в копилку эаа +1")
    elif text == "топ эаа":
        top = sorted(eaa_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = [f"{i+1}. @{user} - {count}" for i, (user, count) in enumerate(top)]
        reply = "*Эаа*\n" + "\n".join(lines)
        bot.reply_to(message, reply, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text.startswith("run"))
def execute_lua(message):
    code = message.text[len("run"):].strip()
    output = []

    def py_print(*args):
        output.append(" ".join(str(arg) for arg in args))

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals()["print"] = py_print

    try:
        lua.execute(code)
        if output:
            result = "\n".join(output)
            escaped_output = escape_markdown(result)
            escaped_code = escape_markdown(code)
            msg = f"*Callback:*\n```lua\n{escaped_output}\n```\n*Your Code:*\n```lua\n{escaped_code}\n```"
        else:
            escaped_code = escape_markdown(code)
            msg = f"*Successfully runned!*\n```lua\n{escaped_code}\n```"
    except Exception as e:
        escaped_error = str(e).replace('`', "'")
        escaped_code = escape_markdown(code)
        msg = f"*Callback:*\n`{escaped_error}`\n*Your Code:*\n```lua\n{escaped_code}\n```"

    bot.reply_to(message, msg, parse_mode="MarkdownV2", reply_to_message_id=message.message_id)

@bot.message_handler(func=lambda message: message.text.startswith("obfuscate"))
def obfuscate_lua(message):
    code = message.text[len("obfuscate"):].strip()
    obfuscated = lua_obfuscate(code)
    escaped_obfuscated = escape_markdown(obfuscated)
    msg = f"*Lua Obfuscated:*\n```lua\n{escaped_obfuscated}\n```"
    bot.reply_to(message, msg, parse_mode="MarkdownV2", reply_to_message_id=message.message_id)

@bot.message_handler(func=lambda message: message.text.startswith("deobfuscate"))
def deobfuscate_lua(message):
    code = message.text[len("deobfuscate"):].strip()
    result = lua_deobfuscate(code)
    escaped_result = escape_markdown(result)
    msg = f"*Lua Deobfuscated:*\n```lua\n{escaped_result}\n```"
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
