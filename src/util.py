from loguru import logger
import os
import sys


ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | {module} | {function} | {level} | {message}"
logger.remove()


def info_only(record):
    return record["level"].name == "INFO"


logger.add(sys.stderr, format=log_format, level="INFO", filter=info_only)
logger.add(ROOT_DIR + '/logs/error.{time:YYYY-MM-DD}.log', format=log_format, level="ERROR", retention='1 days')


