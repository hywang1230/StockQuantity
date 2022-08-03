from src.db.base import *


class TradeOrderRecord(BaseModel):
    id = IntegerField(primary_key=True)
    stock_code = CharField()
    market = CharField()
    strategy = CharField()
    order_id = CharField(unique=True)
    price = DecimalField()
    quantity = IntegerField(null=True)
    side = IntegerField(null=True)
    order_time = DateTimeField()
    status = IntegerField(constraints=[SQL("DEFAULT 0")])
    fee = DecimalField(constraints=[SQL("DEFAULT 0.00000000")], null=True)
    finish_time = DateTimeField(null=True)
    gmt_create = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])
    gmt_modified = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")])

    class Meta:
        table_name = 'trade_order_record'


def save_record(stock_code: str, market: StockMarket, strategy: Strategy, order_id: str, price: Decimal, quantity: int,
                side: StockOrderSide) -> None:
    trade_order_record = TradeOrderRecord()
    trade_order_record.stock_code = stock_code
    trade_order_record.market = market.value
    trade_order_record.strategy = strategy.value
    trade_order_record.order_id = order_id
    trade_order_record.price = price
    trade_order_record.quantity = quantity
    trade_order_record.side = side.value
    trade_order_record.order_time = datetime.datetime.now()
    try:
        trade_order_record.save()
        logger.info('save record success, record={}', trade_order_record)
    except:
        logger.exception('save record error, record={}', trade_order_record)


def update_record(record: TradeOrderRecord):
    try:
        query = TradeOrderRecord.update(price=record.price,
                                        status=record.status,
                                        finish_time=record.time,
                                        fee=record.fee)\
            .where(TradeOrderRecord.order_id == record.order_id)
        query.execute()

        logger.info('update record success, record={}', record)
    except:
        logger.exception('update record error, record={}', record)
