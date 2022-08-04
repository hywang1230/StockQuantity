from loguru import logger
import os
import sys
from src.order_enum import *

ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {module} | {function} | {level} | {message}"
logger.remove()


def info_only(record):
    return record["level"].name == "INFO"


logger.add(ROOT_DIR + '/logs/app.{time:YYYY-MM-DD}.log', format=log_format, level="INFO", filter=info_only,
           retention='1 days')
logger.add(ROOT_DIR + '/logs/error.{time:YYYY-MM-DD}.log', format=log_format, level="ERROR", retention='1 days')


def calculate_fee(price, qty, side: StockOrderSide, market=StockMarket.US, no_commission=False):
    if market == StockMarket.HK:
        return 0

    total = price * qty
    is_sell = side == StockOrderSide.SELL
    fee = (0 if no_commission else max(1, round(qty * 0.005, 2))) \
          + max(1, round(qty * 0.005, 2)) + round(qty * 0.003, 2) \
          + (max(0.01, round(total * 0.0000229, 2)) if is_sell else 0) \
          + (min(5.95, max(0.01, round(qty * 0.000119, 2))) if is_sell else 0)

    return fee


def calculate_amplitude_price(base_price, grid_config, is_up):
    base_price = float(base_price)
    if is_up:
        base_price = base_price * (
                1 + float(grid_config.rise_amplitude)) if grid_config.amplitude_type == 1 \
            else base_price + float(grid_config.rise_amplitude)
    else:
        base_price = base_price * (
                1 - float(grid_config.rise_amplitude)) if grid_config.amplitude_type == 1 \
            else base_price - float(grid_config.rise_amplitude)
    return base_price
