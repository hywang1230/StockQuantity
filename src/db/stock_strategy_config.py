from src.db.base import *
from src.util import *
from src.order_enum import StockOrderSide, Strategy
from decimal import Decimal


class StockStrategyConfig(BaseModel):
    id = IntegerField(primary_key=True)
    stock_code = CharField()
    strategy = CharField()
    market = CharField()
    single_sell_quantity = IntegerField()
    single_buy_quantity = IntegerField()
    remaining_buy_quantity = IntegerField()
    remaining_sell_quantity = IntegerField()
    base_price = DecimalField()
    ext_info = CharField()
    order_account = IntegerField()
    gmt_create = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    gmt_modified = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:
        table_name = 'stock_strategy_config'
        indexes = (
            (('stock_code', 'strategy'), True),
        )


def query_strategy_config(stock_code: str, strategy: Strategy) -> StockStrategyConfig:
    try:
        return StockStrategyConfig.get(stock_code=stock_code, strategy=strategy.value)
    except DoesNotExist:
        logger.info('not exist stock strategy config: stock_code={}, strategy={}', stock_code, strategy.value)


def query_all_config(strategy: Strategy):
    return StockStrategyConfig.select().where(StockStrategyConfig.strategy == strategy.value)


def update_reminder_quantity(config_id: int, quantity: int, side: StockOrderSide):
    try:
        config = StockStrategyConfig.get(StockStrategyConfig.id == config_id)
        remaining_sell_quantity = config.remaining_sell_quantity - quantity if side == StockOrderSide.SELL \
            else config.remaining_sell_quantity + quantity

        remaining_buy_quantity = config.remaining_buy_quantity + quantity if side == StockOrderSide.SELL \
            else config.remaining_buy_quantity - quantity

        query = StockStrategyConfig.update(remaining_sell_quantity=remaining_sell_quantity,
                                           remaining_buy_quantity=remaining_buy_quantity) \
            .where(StockStrategyConfig.id == config_id)

        query.execute()
        logger.info('update reminder quantity success, id={}, quantity={}, side={}', config_id, quantity, side.name)
    except:
        logger.exception('update reminder quantity error, id={}, quantity={}, side={}', config_id, quantity, side.name)


def update_base_price(config_id: int, price: Decimal):
    try:
        query = StockStrategyConfig.update(base_price=price) \
            .where(StockStrategyConfig.id == config_id)

        query.execute()
        logger.info('update base price success, id={}, price={}', config_id, price)
    except:
        logger.exception('update base price error, id={}, price={}', config_id, price)
