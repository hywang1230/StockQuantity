from loguru import logger
import os
from src.order_enum import *
from src.telegram_notify import *
import math

ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

RISE_AMPLITUDE_KEY = 'rise_amplitude'
FALL_AMPLITUDE_KEY = 'fall_amplitude'
AMPLITUDE_TYPE_KEY = 'amplitude_type'
TRAILING_KEY = 'trailing'

log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {module} | {function} | {level} | {message}"
logger.remove()


def info_and_warning(record):
    return record["level"].name in ("INFO", "WARNING")


logger.add(ROOT_DIR + '/logs/app.log', format=log_format, level="INFO", filter=info_and_warning)
logger.add(ROOT_DIR + '/logs/error.log', format=log_format, level="ERROR")
logger.add(CustomHandler(), level="WARNING", format="{message}")


def calculate_fee(price, qty, side: StockOrderSide, market=StockMarket.US, no_commission=False, is_eft=False):
    total = price * qty
    is_sell = side == StockOrderSide.SELL

    if market == StockMarket.HK:
        fee = (0 if no_commission else max(3, round(qty * 0.0003, 2))) + 15.5 \
              + (0 if is_eft else math.ceil(0.0013 * total)) + max(0.01, round(total * 0.00005, 2)) \
              + max(0.01, round(total * 0.000027, 2)) + max(0.01, round(total * 0.0000015, 2)) \
              + min(100, max(2, round(total * 0.00002, 2)))
    else:
        fee = (0 if no_commission else max(1, round(qty * 0.005, 2))) \
          + max(1, round(qty * 0.005, 2)) + round(qty * 0.003, 2) \
          + (max(0.01, round(total * 0.0000229, 2)) if is_sell else 0) \
          + (min(5.95, max(0.01, round(qty * 0.000119, 2))) if is_sell else 0)

    return fee


def calculate_amplitude_price(base_price, config: str | dict, is_up: bool):
    base_price = float(base_price)

    if type(config) == str:
        config = eval(config)

    if is_up:
        base_price = base_price * (
                1 + float(config[RISE_AMPLITUDE_KEY])) if config[AMPLITUDE_TYPE_KEY] == 1 \
            else base_price + float(config[RISE_AMPLITUDE_KEY])
    else:
        base_price = base_price * (
                1 - float(config[FALL_AMPLITUDE_KEY])) if config[AMPLITUDE_TYPE_KEY] == 1 \
            else base_price - float(config[FALL_AMPLITUDE_KEY])
    return base_price
