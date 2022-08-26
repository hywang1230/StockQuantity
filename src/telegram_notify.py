from logging import LogRecord

import telebot
import logging
from src.configuration import TgConfiguration

tg_configuration = TgConfiguration()
API_TOKEN = tg_configuration.api_token

bot = telebot.TeleBot(API_TOKEN)


class CustomHandler(logging.Handler):

    def emit(self, record: LogRecord) -> None:
        bot.send_message(tg_configuration.chat_id, record.msg)
