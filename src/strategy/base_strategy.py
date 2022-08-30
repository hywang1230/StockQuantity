import time

from src.configuration import FutuConfiguration
from src.db import *
import futu
import pandas as pd
from src.util import *
import datetime
import threading
import longbridge.openapi as lb
from decimal import Decimal

pd.set_option('display.max_rows', 5000)
pd.set_option('display.max_columns', 5000)
pd.set_option('display.width', 1000)
futu.SysConfig.enable_proto_encrypt(is_encrypt=True)
futu.SysConfig.set_init_rsa_file(ROOT_DIR + "/rsa")

order_id_set = set()


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
        self.__trd_ctx_dict = {StockMarket.US: futu.OpenSecTradeContext(filter_trdmarket=futu.TrdMarket.US,
                                                                        host=config.host,
                                                                        port=config.port,
                                                                        security_firm=futu.SecurityFirm.FUTUSECURITIES),
                               StockMarket.HK: futu.OpenSecTradeContext(filter_trdmarket=futu.TrdMarket.HK,
                                                                        host=config.host,
                                                                        port=config.port,
                                                                        security_firm=futu.SecurityFirm.FUTUSECURITIES)}

        for ctx in self.__trd_ctx_dict.values():
            ctx.unlock_trade(password_md5=config.unlock_password_md5)

    def __init_quote_context(self):
        config = FutuConfiguration()
        self.__quote_ctx = futu.OpenQuoteContext(host=config.host, port=config.port)

    def get_trade_context(self, market: StockMarket) -> futu.OpenSecTradeContext:
        return self.__trd_ctx_dict.get(market)

    def get_quote_context(self) -> futu.OpenQuoteContext:
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
        self.__trade_context = lb.TradeContext(auth_config)

    def get_trade_context(self) -> lb.TradeContext:
        return self.__trade_context

    def __refresh_token(self):
        config = longbridge_auth.get_auth()
        now = datetime.datetime.now().date()
        if config.token_expired_time - datetime.timedelta(days=30) < now:
            auth_config = self.__get_config()
            resp = auth_config.refresh_access_token()
            longbridge_auth.update_token(resp, datetime.datetime.now().date() + datetime.timedelta(days=90))

    @staticmethod
    def __get_config():
        config = longbridge_auth.get_auth()
        return lb.Config(app_key=config.app_key, app_secret=config.app_secret, access_token=config.access_token)


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
        if (strategy_config.market == 'US' and '04:00:10' < now < '21:29:50') \
                or (strategy_config.market == 'HK' and (now < '09:29:50' or now > '16:00:10')):
            logger.info('{} is not in trade time', now)
            return False

        lock = OrderLock.instance()
        if not (lock.lock(stock_code, strategy, side)):
            logger.error('stock_code={}, strategy={},side={} lock fail', stock_code, strategy, side)
            return False

        # check reminder quantity > 0
        reminder_quantity = strategy_config.remaining_sell_quantity if side == StockOrderSide.SELL \
            else strategy_config.remaining_buy_quantity
        if reminder_quantity <= 0:
            logger.info('stock_code={}, strategy={},side={} reminder_quantity is zero', stock_code, strategy, side)
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


class LongbridgeOrder(BaseStrategy):

    def place_order(self, stock_code: str, market: StockMarket, price: Decimal, qty: int, side: StockOrderSide):
        try:
            resp = LongbridgeContext.instance().get_trade_context().submit_order(
                side=lb.OrderSide.Sell if side == StockOrderSide.SELL else lb.OrderSide.Buy,
                symbol=stock_code + '.' + market.value,
                order_type=lb.OrderType.MO,
                submitted_quantity=qty,
                outside_rth=lb.OutsideRTH.RTHOnly,
                time_in_force=lb.TimeInForceType.Day
            )

            order_id = resp.order_id

            logger.warning('order success, stock_code={}, price={}, quantity={}, is_sell={}, order_id={}', stock_code,
                           price, qty,
                           side.name,
                           order_id)
            return True, order_id

        except:
            logger.exception('order success, stock_code={}, price={}, quantity={}, is_sell={}', stock_code,
                             price, qty, side)
        return False, None


class FutuOrder(BaseStrategy):

    def place_order(self, stock_code: str, market: StockMarket, price: Decimal, qty: int, side: StockOrderSide):
        trd_side = futu.TrdSide.SELL if side == StockOrderSide.SELL else futu.TrdSide.BUY

        ret, data = FutuContext.instance().get_trade_context(market).place_order(price=price, qty=qty, code=stock_code,
                                                                                 trd_side=trd_side,
                                                                                 fill_outside_rth=False,
                                                                                 order_type=futu.OrderType.MARKET,
                                                                                 trd_env=futu.TrdEnv.REAL)
        if ret == futu.RET_OK:
            order_id = data['order_id'][0]
            logger.warning('place order success, stock_code={}, price={}, quantity={}, side={}, order_id={}',
                           stock_code,
                           price, qty,
                           side, order_id)

            return True, order_id
        else:
            logger.warning('place order fail, stock_code={}, price={}, quantity={}, side={}, error={}', stock_code,
                           price, qty,
                           side, data)
            return False, None


class OrderInfo:

    def __init__(self) -> None:
        self.stock_code = None
        self.order_status = None
        self.price = None
        self.order_id = None
        self.stock_grid_id = None


class Observer:
    def update_strategy(self, orderInfo: OrderInfo):
        pass


class Subject:

    def __init__(self) -> None:
        self.observers = {}

    def subscribe(self, grid: Strategy, observer: Observer) -> None:
        self.observers[grid] = observer

    def unsubscribe(self, grid: Strategy) -> None:
        self.observers.pop(grid)

    def notify(self, grid: Strategy, order_info: OrderInfo):
        self.observers[grid].update_strategy(order_info)


subject = Subject()


def on_order_changed(event: lb.PushOrderChanged):
    """
    长桥的订单状态推送
    :param event: 订单状态变更事件
    :return:
    """
    logger.info("receive order changed msg:{}", event)

    order_status = event.status
    if order_status in (lb.OrderStatus.Canceled, lb.OrderStatus.Filled):
        order_status = StockOrderStatus.SUCCESS if order_status == lb.OrderStatus.Filled else StockOrderStatus.CANCELED
        stock_code = event.symbol.split('.')[0]
        stock_code = stock_code.zfill(5) if event.symbol.split('.')[-1] == 'HK' else stock_code

        order_id = event.order_id

        if order_id in order_id_set:
            return

        order_id_set.add(order_id)

        order_info = OrderInfo()
        order_info.stock_code = stock_code
        order_info.order_status = order_status
        order_info.price = event.executed_price if order_status == StockOrderStatus.SUCCESS else event.submitted_price
        order_info.order_id = order_id

        after_order(order_info)


class TradeOrderHandler(futu.TradeOrderHandlerBase):
    """ order update push"""

    def on_recv_rsp(self, rsp_pb):
        ret, content = super(TradeOrderHandler, self).on_recv_rsp(rsp_pb)
        logger.info('receive trade order msg, content: {}', content)
        if ret == futu.RET_OK:
            if content['trd_env'][0] == 'SIMULATE':
                return

            order_status = content['order_status'][0]
            if order_status not in ('CANCELLED_ALL', 'FILLED_ALL'):
                return

            order_id = content['order_id'][0]

            if order_id in order_id_set:
                return

            order_id_set.add(order_id)

            order_status = StockOrderStatus.SUCCESS if order_status == 'FILLED_ALL' else StockOrderStatus.CANCELED
            stock_code = content['code'][0].split('.')[-1]

            order_info = OrderInfo()
            order_info.stock_code = stock_code
            order_info.order_status = order_status
            order_info.price = content['dealt_avg_price'][0]
            order_info.order_id = order_id

            after_order(order_info)


def after_order(order_info: OrderInfo):
    logger.info('deal after order, order_id={}', order_info.order_id)
    order_record = trade_order_record.query_record(order_info.order_id)
    if order_record is None:
        time.sleep(10)
        order_record = trade_order_record.query_record(order_info.order_id)
        if order_record is None:
            logger.info('order record is null, order_id', order_info.order_id)

    strategy_config = stock_strategy_config.query_strategy_config(order_record.stock_code,
                                                                  Strategy(order_record.strategy))

    if strategy_config is None:
        logger.info('no strategy config, stock_code={}, strategy={}', order_record.stock_code,
                    Strategy(order_record.strategy).name)
        return

    order_info.stock_grid_id = strategy_config.id

    fee = 0 if order_info.order_status == StockOrderStatus.CANCELED else \
        calculate_fee(order_info.price, order_record.quantity, StockOrderSide(order_record.side),
                      StockMarket(order_record.market), strategy_config.order_account == OrderAccount.LONGBRIDGE.value)
    trade_order_record.update_record(order_info.order_id, order_info.price, order_info.order_status, fee)

    if order_info.order_status == StockOrderStatus.SUCCESS:
        stock_strategy_config.update_reminder_quantity(strategy_config.id, order_record.quantity,
                                                       StockOrderSide(order_record.side))

    subject.notify(Strategy(order_record.strategy), order_info)
