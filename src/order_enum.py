from enum import Enum


class OrderSide(Enum):
    SELL = 1
    BUY = 2


class Market(Enum):
    US = 'US'
    HK = 'HK'


class Strategy(Enum):
    GRID = 'grid'
