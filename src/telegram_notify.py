from logging import LogRecord

import telebot
import logging

API_TOKEN = '5473494665:AAFcycDH0hjbUubMTV6CW2Swb55sOOtlgM4'

bot = telebot.TeleBot(API_TOKEN)


class CustomHandler(logging.Handler):

    def emit(self, record: LogRecord) -> None:
        bot.send_message(179393813, record.msg)
