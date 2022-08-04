from enum import Enum


class StockOrderSide(Enum):
    SELL = 1
    BUY = 2


class StockMarket(Enum):
    US = 'US'
    HK = 'HK'


class Strategy(Enum):
    GRID = 'grid'


class StockOrderStatus(Enum):
    SUBMIT = 0
    SUCCESS = 1
    FAIL = 2
    CANCELED = 3


class OrderAccount(Enum):
    FUTU = 1
    LONGBRIDGE = 2
