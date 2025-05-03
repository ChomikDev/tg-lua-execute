import telebot
from flask import Flask, request
from lupa import LuaRuntime
import re
import os

API_TOKEN = os.getenv("BOT_TOKEN")  # Токен бота из переменной окружения
bot = telebot.TeleBot(API_TOKEN)
app = Flask(__name__)

WEBHOOK_PATH = f"/{API_TOKEN}"
WEBHOOK_URL = f"https://tg-lua-execute.onrender.com{WEBHOOK_PATH}"  # Заменить на свой URL

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

@bot.message_handler(func=lambda message: message.text.startswith("execute"))
def execute_lua(message):
    code = message.text[len("execute"):].strip()
    output = []

    def py_print(*args):
        output.append(" ".join(str(arg) for arg in args))

    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals()["print"] = py_print

    try:
        lua.execute(code)
        if output:
            result = "\n".join(output)
            escaped = escape_markdown(result)
            msg = f"*Callback:*\n```lua\n{escaped}\n```"
        else:
            msg = "*Script successfully executed!*"
    except Exception as e:
        escaped = escape_markdown(str(e))
        msg = f"*Lua error:*\n```lua\n{escaped}\n```"

    bot.send_message(message.chat.id, msg, parse_mode="MarkdownV2", reply_to_message_id=message.message_id)

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return 'Bot is running (Webhook mode)'

# Установить Webhook при старте
if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
