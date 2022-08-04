from src.configuration import FutuConfiguration
from src.db import *
from futu import *
import pandas as pd
from src.util import *
import datetime
import threading
from longbridge.openapi import *
from decimal import Decimal
import queue

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
        self.__trd_ctx_dict = {StockMarket.US: OpenSecTradeContext(filter_trdmarket=TrdMarket.US, host=config.host,
                                                                   port=config.port,
                                                                   security_firm=SecurityFirm.FUTUSECURITIES),
                               StockMarket.HK: OpenSecTradeContext(filter_trdmarket=TrdMarket.HK, host=config.host,
                                                                   port=config.port,
                                                                   security_firm=SecurityFirm.FUTUSECURITIES)}

        for ctx in self.__trd_ctx_dict.values():
            ctx.unlock_trade(password_md5=config.unlock_password_md5)

    def __init_quote_context(self):
        config = FutuConfiguration()
        self.__quote_ctx = OpenQuoteContext(host=config.host, port=config.port)

    def get_trade_context(self, market: StockMarket) -> OpenSecTradeContext:
        return self.__trd_ctx_dict.get(market)

    def get_quote_context(self) -> OpenQuoteContext:
        return self.__quote_ctx


class LongbridgeContext(object):
    _instance = None

    __trade_context = None

    def __init__(self):
        raise RuntimeError('Call instance() instead')

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)

            cls.__init_trade_context(cls._instance)
        return cls._instance

    def __init_trade_context(self):
        self.__refresh_token()
        auth_config = self.__get_config()
        self.__trade_context = TradeContext(auth_config)

    def get_trade_context(self) -> TradeContext:
        return self.__trade_context

    def __refresh_token(self):
        auth_config = self.__get_config()
        resp = auth_config.refresh_access_token()
        longbridge_auth.update_token(resp, datetime.datetime.now().date() + datetime.timedelta(days=90))

    @staticmethod
    def __get_config():
        config = longbridge_auth.get_auth()
        return Config(app_key=config.app_key, app_secret=config.app_secret, access_token=config.access_token)


class OrderLock(object):
    _instance = None

    __lock_set = set()

    __lock = threading.Lock()

    def __init__(self):
        raise RuntimeError('Call instance() instead')

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
        return cls._instance

    def lock(self, stock_code, strategy: Strategy, side: StockOrderSide) -> bool:
        lock = threading.Lock()
        lock.acquire()
        key = self.__build_key(stock_code, strategy, side)
        try:
            if key in self.__lock_set:
                return False

            self.__lock_set.add(key)
            return True
        finally:
            lock.release()

    def release_lock(self, stock_code: str, strategy: Strategy, side: StockOrderSide) -> None:
        key = self.__build_key(stock_code, strategy, side)
        self.__lock_set.remove(key)

    @staticmethod
    def __build_key(stock_code, strategy: Strategy, side: StockOrderSide) -> str:
        return stock_code + '|' + strategy.value + '|' + str(side.value)


class BaseStrategy(object):
    def order(self, stock_code: str, strategy: Strategy, price: Decimal, side: StockOrderSide, **kwargs):
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
        reminder_quantity = strategy_config.remaining_sell_quantity if side == StockOrderSide.SELL \
            else strategy_config.remaining_buy_quantity
        if reminder_quantity <= 0:
            logger.info('stock_code={}, strategy={},side={} reminder_quantity is zero', stock_code, strategy, side)
            return False

        lock = OrderLock.instance()
        if not (lock.lock(stock_code, strategy, side)):
            logger.info('stock_code={}, strategy={},side={} lock fail', stock_code, strategy, side)
            return False

        try:
            qty = strategy_config.single_sell_quantity if StockOrderSide.SELL == side \
                else strategy_config.single_buy_quantity
            market = StockMarket[strategy_config.market]
            success, order_id = self.place_order(stock_code, market, price, qty, side)
            if success:
                trade_order_record.save_record(stock_code, market, strategy, order_id, price, qty, side)
            return success
        finally:
            lock.release_lock(stock_code, strategy, side)

    def place_order(self, stock_code: str, market: StockMarket, price: Decimal, qty: int, side: StockOrderSide):
        return False, None


longbridge_order_queue = queue.Queue(maxsize=20)


class LongbridgeOrder(BaseStrategy):

    def place_order(self, stock_code: str, market: StockMarket, price: Decimal, qty: int, side: StockOrderSide):
        try:
            resp = LongbridgeContext.instance().get_trade_context().submit_order(
                side=OrderSide.Sell if side == StockOrderSide.SELL else OrderSide.Buy,
                symbol=stock_code + '.' + market.value,
                order_type=OrderType.MO,
                submitted_quantity=qty,
                outside_rth=OutsideRTH.RTHOnly,
                time_in_force=TimeInForceType.Day
            )

            order_id = resp.order_id

            logger.info('order success, stock_code={}, price={}, quantity={}, is_sell={}, order_id={}', stock_code,
                        price, qty,
                        side.name,
                        order_id)
            longbridge_order_queue.put(order_id)
            return True, order_id

        except:
            logger.exception('order success, stock_code={}, price={}, quantity={}, is_sell={}', stock_code,
                             price, qty, side)
        return False, None


class FutuOrder(BaseStrategy):

    def place_order(self, stock_code: str, market: StockMarket, price: Decimal, qty: int, side: StockOrderSide):
        trd_side = TrdSide.SELL if side == StockOrderSide.SELL else TrdSide.BUY

        ret, data = FutuContext.instance().get_trade_context(market).place_order(price=price, qty=qty, code=stock_code,
                                                                                 trd_side=trd_side,
                                                                                 fill_outside_rth=False,
                                                                                 order_type=OrderType.MARKET,
                                                                                 trd_env=TrdEnv.REAL)
        if ret == RET_OK:
            order_id = data['order_id'][0]
            logger.info('place order success, stock_code={}, price={}, quantity={}, side={}, order_id={}', stock_code,
                        price, qty,
                        side, order_id)

            return True, order_id
        else:
            logger.info('place order success, stock_code={}, price={}, quantity={}, side={}, error={}', stock_code,
                        price, qty,
                        side, data)
            return False, None
