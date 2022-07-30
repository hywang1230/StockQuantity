from src.db.base import *


class GridStrategyConfig(BaseModel):
    id = IntegerField(primary_key=True)
    stock_strategy_id = IntegerField(unique=True)
    base_price = DecimalField()
    rise_amplitude = DecimalField()
    fall_amplitude = DecimalField(null=True)
    amplitude_type = IntegerField(constraints=[SQL("DEFAULT 1")])
    gmt_create = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    gmt_modified = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:
        table_name = 'grid_strategy_config'


def query_strategy_config(stock_strategy_id: int):
    try:
        return GridStrategyConfig.get(stock_strategy_id=stock_strategy_id)
    except DoesNotExist:
        logger.info('not exist grid strategy config: stock_strategy_id={}', stock_strategy_id)


def update_base_price(stock_strategy_id: int, price: Decimal):
    try:
        query = GridStrategyConfig.update(base_price=price) \
            .where(GridStrategyConfig.stock_strategy_id == stock_strategy_id)

        query.execute()
        logger.info('update base price success, stock_strategy_id={}, price={}', stock_strategy_id, price)
    except:
        logger.exception('update base price error, stock_strategy_id={}, price={}', stock_strategy_id, price)
