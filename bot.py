import os
import telebot
from lupa import LuaRuntime
import re

# Получаем токен из переменной окружения
bot = telebot.TeleBot(os.environ["BOT_TOKEN"])

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
            escaped_result = escape_markdown(result)
            text = f"*Callback:*\n```lua\n{escaped_result}\n```"
        else:
            text = "*Script successfully executed!*"
        bot.send_message(
            message.chat.id,
            text,
            parse_mode="MarkdownV2",
            reply_to_message_id=message.message_id
        )
    except Exception as e:
        escaped_error = escape_markdown(str(e))
        bot.send_message(
            message.chat.id,
            f"*Lua error:*\n```lua\n{escaped_error}\n```",
            parse_mode="MarkdownV2",
            reply_to_message_id=message.message_id
        )

bot.infinity_polling()
