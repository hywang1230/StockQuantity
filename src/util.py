from loguru import logger
import os
import sys

from src.db.grid_strategy_config import GridStrategyConfig

ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {module} | {function} | {level} | {message}"
logger.remove()


def info_only(record):
    return record["level"].name == "INFO"


logger.add(sys.stderr, format=log_format, level="INFO", filter=info_only)
logger.add(ROOT_DIR + '/logs/error.{time:YYYY-MM-DD}.log', format=log_format, level="ERROR", retention='1 days')


def calculate_fee(price, qty, is_sell, market='US'):
    if market == 'HK':
        return 0

    total = price * qty
    fee = max(1, round(qty * 0.005, 2)) + round(qty * 0.003, 2) \
          + (max(0.01, round(total * 0.0000229, 2)) if is_sell else 0) \
          + (min(5.95, max(0.01, round(qty * 0.000119, 2))) if is_sell else 0)

    return fee


def calculate_amplitude_price(base_price, grid_config: GridStrategyConfig, is_up):
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
