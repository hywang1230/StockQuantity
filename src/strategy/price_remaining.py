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
        success = FutuOrder().order(stock_code, Strategy.GRID, Decimal(price), side) \
            if strategy_config.order_account == 1 \
            else LongbridgeOrder().order(stock_code, Strategy.GRID, Decimal(price), side)

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


order_id_set = set()
def on_order_changed(event: PushOrderChanged):
    """
    长桥的订单状态推送
    :param event: 订单状态变更事件
    :return:
    """
    logger.info("receive order changed msg:{}", event)

    order_status = event.status
    if order_status in (OrderStatus.Canceled, OrderStatus.Filled):
        order_status = StockOrderStatus.SUCCESS if order_status == OrderStatus.Filled else StockOrderStatus.CANCELED
        stock_code = event.symbol.split('.')[0]
        stock_code = stock_code.zfill(5) if event.symbol.split('.')[-1] == 'HK' else stock_code
        strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

        if strategy_config is None:
            logger.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
            return

        order_id = event.order_id

        if order_id in order_id_set:
            return

        order_id_set.add(order_id)

        grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)
        price = event.executed_price if order_status == StockOrderStatus.SUCCESS else event.submitted_price

        base_price = grid_config.base_price
        side = StockOrderSide.SELL if event.side == OrderSide.Sell else StockOrderSide.BUY
        market = StockMarket[strategy_config.market]
        qty = event.executed_quantity
        after_order(strategy_config, grid_config, order_status, price, base_price, qty, side, market, order_id)


class TradeOrderHandler(TradeOrderHandlerBase):
    """ order update push"""

    def on_recv_rsp(self, rsp_pb):
        ret, content = super(TradeOrderHandler, self).on_recv_rsp(rsp_pb)
        logger.info('receive trade order msg, content: {}', content)
        if ret == RET_OK:
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
            strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

            if strategy_config is None:
                logger.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
                return
            grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)
            price = content['dealt_avg_price'][0]

            base_price = grid_config.base_price
            side = StockOrderSide.SELL if content['trd_side'][0] in ('SELL', 'SELL_SHORT') else StockOrderSide.BUY
            market = StockMarket[strategy_config.market]

            qty = content['dealt_qty'][0]
            after_order(strategy_config, grid_config, order_status, price, base_price, qty, side, market, order_id,
                        False)


def after_order(strategy_config, grid_config, order_status: StockOrderStatus, price, base_price, qty,
                side: StockOrderSide, market: StockMarket, order_id, no_commission=True):
    fee = 0 if order_status == StockOrderStatus.CANCELED else \
        calculate_fee(price, qty, side, market, no_commission)
    trade_order_record.update_record(order_id, price, order_status, fee)

    if order_status == StockOrderStatus.SUCCESS:
        base_price = calculate_amplitude_price(base_price, grid_config, side == StockOrderSide.SELL)

        grid_strategy_config.update_base_price(grid_config.id, base_price)
        stock_strategy_config.update_reminder_quantity(strategy_config.id, qty, side)

    reset_price_reminder(strategy_config)


def query_order_status_task():
    while True:
        order_id = longbridge_order_queue.get()

        resp = LongbridgeContext.instance().get_trade_context().today_orders(order_id=order_id)
        logger.info("query order status, order_id={}, resp={}", order_id, resp)
        order_info = resp[0]
        order_status = order_info.status
        if order_status in (OrderStatus.Canceled, OrderStatus.Filled, OrderStatus.Rejected):
            order_status = StockOrderStatus.SUCCESS if order_status == OrderStatus.Filled \
                else StockOrderStatus.CANCELED
            stock_code = order_info.symbol.split('.')[0]
            stock_code = stock_code.zfill(5) if order_info.symbol.split('.')[-1] == 'HK' else stock_code
            strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

            if strategy_config is None:
                logger.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
                return
            grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)
            price = order_info.executed_price if order_status == StockOrderStatus.SUCCESS else order_info.price
            base_price = grid_config.base_price
            side = StockOrderSide.SELL if order_info.side == OrderSide.Sell else StockOrderSide.BUY
            market = StockMarket[strategy_config.market]
            qty = order_info.executed_quantity
            after_order(strategy_config, grid_config, order_status, price, base_price, qty, side, market, order_id)
        else:
            longbridge_order_queue.put(order_id)
            sleep(1)


def has_longbridge(strategy_config_list):
    for strategy_config in strategy_config_list:
        if strategy_config.order_account == OrderAccount.LONGBRIDGE.value:
            return True

    return False


def has_futu_us(strategy_config_list):
    for strategy_config in strategy_config_list:
        if strategy_config.order_account == OrderAccount.FUTU.value and strategy_config.market == StockMarket.US.value:
            return True

    return False


def has_futu_hk(strategy_config_list):
    for strategy_config in strategy_config_list:
        if strategy_config.order_account == OrderAccount.FUTU.value and strategy_config.market == StockMarket.HK.value:
            return True

    return False


def init():
    strategy_config_list = stock_strategy_config.query_all_config(Strategy.GRID)

    if strategy_config_list is not None:
        if has_longbridge(strategy_config_list):
            # t = threading.Thread(target=query_order_status_task)
            # t.start()
            LongbridgeContext.instance().get_trade_context().set_on_order_changed(on_order_changed)
            LongbridgeContext.instance().get_trade_context().subscribe([TopicType.Private])
            print('set longbridge success')

        if has_futu_us(strategy_config_list):
            FutuContext.instance().get_trade_context(StockMarket.US).set_handler(TradeOrderHandler())
            print('set futu us success')

        if has_futu_hk(strategy_config_list):
            FutuContext.instance().get_trade_context(StockMarket.HK).set_handler(TradeOrderHandler())
            print('set futu hk success')

        FutuContext.instance().get_quote_context().set_handler(PriceReminder())

    for strategy_config in strategy_config_list:
        reset_price_reminder(strategy_config)

    print('price_reminder start success...')
