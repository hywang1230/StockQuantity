from src.strategy.base_strategy import *
from time import sleep


class PriceReminder(PriceReminderHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        ret_code, content = super(PriceReminder, self).on_recv_rsp(rsp_pb)
        logger.info('receive price reminder msg, content: {}', content)
        if ret_code != RET_OK:
            logger.error("PriceReminder: error, msg: {}", content)
            return

        stock_code = content['code'].split(".")[-1]
        strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

        if strategy_config is None:
            logger.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
            return

        price = content['price']
        side = StockOrderSide.SELL if content['reminder_type'] == 'PRICE_UP' else StockOrderSide.BUY
        success = LongbridgeOrder().order(stock_code, Strategy.GRID, Decimal(price), side)

        if not success:
            reset_price_reminder(strategy_config)


def reset_price_reminder(strategy_config):
    """
    重置到价提醒，先删除后新增
    :param strategy_config: 配置信息
    """
    grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)

    quote_ctx = FutuContext.instance().get_quote_context()
    code = strategy_config.market + '.' + strategy_config.stock_code
    ret_ask, ask_data = quote_ctx.set_price_reminder(code=code,
                                                     op=SetPriceReminderOp.DEL_ALL)
    if ret_ask == RET_OK:
        # set price up
        if strategy_config.remaining_sell_quantity > 0:
            reminder_price = calculate_amplitude_price(grid_config.base_price, grid_config, True)
            ret_ask, ask_data = quote_ctx.set_price_reminder(code=code,
                                                             op=SetPriceReminderOp.ADD,
                                                             reminder_type=PriceReminderType.PRICE_UP,
                                                             reminder_freq=PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == RET_OK:
                logger.info('set price up success, stock_code={}, reminder_price={}', strategy_config.stock_code,
                            reminder_price)
            else:
                logger.error('error:{}', ask_data)

        # set price down
        if strategy_config.remaining_buy_quantity > 0:
            reminder_price = calculate_amplitude_price(grid_config.base_price, grid_config, False)

            ret_ask, ask_data = quote_ctx.set_price_reminder(code,
                                                             op=SetPriceReminderOp.ADD,
                                                             reminder_type=PriceReminderType.PRICE_DOWN,
                                                             reminder_freq=PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == RET_OK:
                logger.info('set price down success, stock_code={}, reminder_price={}', strategy_config.stock_code,
                            reminder_price)
            else:
                logger.error('set price down error:{}', ask_data)

    else:
        logger.error('set price up error:{}', ask_data)


def on_order_changed(event: PushOrderChanged):
    logger.info("receive order changed msg:{}", event)

    order_status = event.status
    if order_status in (OrderStatus.Canceled, OrderStatus.Filled):
        order_status = StockOrderStatus.SUCCESS if order_status == OrderStatus.Filled else StockOrderStatus.CANCELED
        stock_code = event.symbol.split('.')[0].zfill(5)
        strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

        if strategy_config is None:
            logger.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
            return
        grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)
        price = event.executed_price if order_status == StockOrderStatus.SUCCESS else event.submitted_price
        order_id = event.order_id
        finish_time = event.updated_at
        base_price = grid_config.base_price
        side = StockOrderSide.SELL if event.side == OrderSide.Sell else StockOrderSide.BUY
        market = StockMarket[strategy_config.market]
        qty = event.executed_quantity
        fee = 0 if order_status == StockOrderStatus.CANCELED else \
            calculate_fee(price, qty, side, market)
        trade_order_record.update_record(order_id, price, order_status, finish_time, fee)

        if order_status == StockOrderStatus.SUCCESS:
            base_price = calculate_amplitude_price(base_price, grid_config, side == StockOrderSide.SELL)

            grid_strategy_config.update_base_price(grid_config.id, base_price)
            stock_strategy_config.update_reminder_quantity(strategy_config.id, qty, side)

        reset_price_reminder(strategy_config)


class MyThread(threading.Thread):

    def run(self) -> None:
        print(1)
        LongbridgeContext.instance().get_trade_context().set_on_order_changed(on_order_changed)
        LongbridgeContext.instance().get_trade_context().subscribe([TopicType.Private])
        # condition = threading.Condition()
        # condition.acquire()
        # condition.wait()
        # print(2)
        while True:
            sleep(1)
            print('---------' + datetime.datetime.now().strftime('%H:%M:%S'))


def init():
    strategy_config_list = stock_strategy_config.query_all_config(Strategy.GRID)

    if strategy_config_list is not None:
        MyThread().start()
        FutuContext.instance().get_quote_context().set_handler(PriceReminder())

    # for strategy_config in strategy_config_list:
    #     reset_price_reminder(strategy_config)
    print('price_reminder start success...')

