from peewee import *
from playhouse.shortcuts import ReconnectMixin
from src.configuration import DbConfiguration
from src.util import *
from decimal import Decimal
from src.order_enum import StockOrderSide, StockMarket, Strategy, StockOrderStatus
import datetime
from decimal import Decimal

db_configuration = DbConfiguration()

db_setting = {'charset': 'utf8', 'sql_mode': 'PIPES_AS_CONCAT', 'use_unicode': True,
              'host': db_configuration.host,
              'port': db_configuration.port,
              'user': db_configuration.user,
              'password': db_configuration.password}


class ReconnectMySQLDatabase(ReconnectMixin, MySQLDatabase):
    def sequence_exists(self, seq):
        pass


database = ReconnectMySQLDatabase(db_configuration.database, **db_setting)


class UnknownField(object):
    def __init__(self, *_, **__): pass


class BaseModel(Model):
    class Meta:
        database = database

    def __str__(self):
        return '%s(%s)' % (
            type(self).__name__,
            ', '.join('%s=%s' % item for item in vars(self).items())
        )

