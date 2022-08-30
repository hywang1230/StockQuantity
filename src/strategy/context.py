from src.configuration import FutuConfiguration
from src.db import *
import futu
import pandas as pd
from src.util import *
import datetime
import longbridge.openapi as lb

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


