from enum import Enum


class StockOrderSide(Enum):
    SELL = 1
    BUY = 2


class StockMarket(Enum):
    US = 'US'
    HK = 'HK'


class Strategy(Enum):
    GRID = 'grid'
