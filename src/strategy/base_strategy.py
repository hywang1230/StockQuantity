from src.configuration import FutuConfiguration
from src.db import *
from src.order_enum import *
from futu import SysConfig, OpenSecTradeContext, OpenQuoteContext, TrdMarket, SecurityFirm, TrdSide, RET_OK, TrdEnv, \
    OrderType
import pandas as pd
from src.util import *
import datetime

pd.set_option('display.max_rows', 5000)
pd.set_option('display.max_columns', 5000)
pd.set_option('display.width', 1000)
SysConfig.enable_proto_encrypt(is_encrypt=True)
SysConfig.set_init_rsa_file(ROOT_DIR + "/rsa")


class FutuContext(object):
    _instance = None

    __trd_ctx_dict = None

    __quote_ctx = None

    def __init__(self):
        raise RuntimeError('Call instance() instead')

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)

            cls.__init_trade_context(cls._instance)
            cls.__init_quote_context(cls._instance)
        return cls._instance

    def __init_trade_context(self):
        config = FutuConfiguration()
        self.__trd_ctx_dict = {Market.US: OpenSecTradeContext(filter_trdmarket=TrdMarket.US, host=config.host,
                                                              port=config.port,
                                                              security_firm=SecurityFirm.FUTUSECURITIES),
                               Market.HK: OpenSecTradeContext(filter_trdmarket=TrdMarket.HK, host=config.host,
                                                              port=config.port,
                                                              security_firm=SecurityFirm.FUTUSECURITIES)}

        for ctx in self.__trd_ctx_dict.values():
            ctx.unlock_trade(password_md5=config.unlock_password_md5)

    def __init_quote_context(self):
        config = FutuConfiguration()
        self.__quote_ctx = OpenQuoteContext(host=config.host, port=config.port)

    def get_trade_context(self, market: Market) -> OpenSecTradeContext:
        return self.__trd_ctx_dict.get(market)

    def get_quote_context(self) -> OpenQuoteContext:
        return self.__quote_ctx


class BaseStrategy(object):
    def order(self, stock_code, strategy: Strategy, price, side: OrderSide, **kwargs):
        strategy_config = stock_strategy_config.query_strategy_config(stock_code, strategy)
        if strategy_config is None:
            logger.info('no strategy config of stock_code={}, strategy={}', stock_code, strategy)
            return False

        # check now is in trade time
        now = datetime.datetime.now().strftime('%H:%M:%S')
        if (strategy_config.market == 'US' and '04:00:00' < now < '21:30:00') \
                or (strategy_config.market == 'HK' and (now < '09:30:00' or now > '16:00:00')):
            logger.info('%s is not in trade time', now)
            return False

        # check reminder quantity > 0
        reminder_quantity = strategy_config.remaining_sell_quantity if side == OrderSide.SELL \
            else strategy_config.remaining_buy_quantity
        if reminder_quantity <= 0:
            logger.info('stock_code={}, strategy={},side={} reminder_quantity is zero', stock_code, strategy, side)
            return False

        trd_side = TrdSide.SELL if side == OrderSide.SELL else TrdSide.BUY
        qty = strategy_config.single_sell_quantity if side == OrderSide.SELL else strategy_config.single_buy_quantity
        stock_code = strategy_config.market + '.' + stock_code
        market = Market[strategy_config.market]
        ret, data = FutuContext.get_trade_context(market).place_order(price=price,
                                                                      qty=qty,
                                                                      code=stock_code,
                                                                      trd_side=trd_side,
                                                                      fill_outside_rth=False,
                                                                      order_type=OrderType.MARKET,
                                                                      trd_env=TrdEnv.REAL)
        if ret == RET_OK:
            logger.info('place order success, stock_code={}, price={}, quantity={}, side={}'.format(stock_code,
                                                                                                    price, qty,
                                                                                                    side))
            order_id = data['order_id'][0]

            return True, order_id
        else:
            logger.error('place_order error: %s', data)

        return False
