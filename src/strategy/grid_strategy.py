from src.strategy.base_strategy import *


monitor_code_dict = {}


class PriceReminder(futu.PriceReminderHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        """
        到价提醒
        :param rsp_pb: 到价提醒信息
        :return:
        """
        ret_code, content = super(PriceReminder, self).on_recv_rsp(rsp_pb)
        logger.info('receive price reminder msg, content: {}', content)
        if ret_code != futu.RET_OK:
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
            reset_price_reminder(strategy_config.stock_code)


class StockQuoteListen(futu.StockQuoteHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        """
        实时报价推送
        :param rsp_pb: 报价信息
        """
        ret_code, data = super(StockQuoteListen, self).on_recv_rsp(rsp_pb)
        if ret_code != futu.RET_OK:
            logger.error("StockQuoteListen: error, msg: {}", data)
            return

        stock_code = data['code'][0].split(".")[-1]

        if stock_code not in monitor_code_dict.keys():
            return

        price = data['last_price'][0]
        price_info = monitor_code_dict[stock_code]
        if ('buy_price' in price_info.keys() and price <= price_info['buy_price']) \
                or ('sell_price' in price_info.keys() and price >= price_info['sell_price']):
            monitor_code_dict.pop(stock_code)

            strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

            if strategy_config is None:
                logger.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
                return

            side = StockOrderSide.SELL if price >= price_info['sell_price'] else StockOrderSide.BUY
            success = FutuOrder().order(stock_code, Strategy.GRID, Decimal(price), side) \
                if strategy_config.order_account == 1 \
                else LongbridgeOrder().order(stock_code, Strategy.GRID, Decimal(price), side)

            if not success:
                reset_price_monitor(strategy_config.stock_code)


class GridObserver(Observer):
    """
    更新网格
    """
    def update_strategy(self, order_info: OrderInfo):
        logger.info('update strategy, order_id={}', order_info.order_id)
        order_record = trade_order_record.query_record(order_info.order_id)
        if order_info.order_status == StockOrderStatus.SUCCESS:
            stock_strategy_config.update_reminder_quantity(order_info.stock_grid_id, order_record.quantity,
                                                           StockOrderSide(order_record.side))

        if order_record.market == StockMarket.US:
            reset_price_reminder(order_info.stock_code)
        else:
            reset_price_monitor(order_info.stock_code)


def reset_price_reminder(stock_code):
    """
    重置到价提醒，先删除后新增
    :param stock_code: 股票代码
    """
    strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

    grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)

    quote_ctx = FutuContext.instance().get_quote_context()
    code = strategy_config.market + '.' + strategy_config.stock_code
    ret_ask, ask_data = quote_ctx.set_price_reminder(code=code,
                                                     op=futu.SetPriceReminderOp.DEL_ALL)
    if ret_ask == futu.RET_OK:
        # set price up
        if strategy_config.remaining_sell_quantity > 0:
            reminder_price = calculate_amplitude_price(grid_config.base_price, grid_config, True)
            ret_ask, ask_data = quote_ctx.set_price_reminder(code=code,
                                                             op=futu.SetPriceReminderOp.ADD,
                                                             reminder_type=futu.PriceReminderType.PRICE_UP,
                                                             reminder_freq=futu.PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == futu.RET_OK:
                logger.warning('set price up success, stock_code={}, reminder_price={}', strategy_config.stock_code,
                               reminder_price)
            else:
                logger.error('error:{}', ask_data)

        # set price down
        if strategy_config.remaining_buy_quantity > 0:
            reminder_price = calculate_amplitude_price(grid_config.base_price, grid_config, False)

            ret_ask, ask_data = quote_ctx.set_price_reminder(code,
                                                             op=futu.SetPriceReminderOp.ADD,
                                                             reminder_type=futu.PriceReminderType.PRICE_DOWN,
                                                             reminder_freq=futu.PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == futu.RET_OK:
                logger.warning('set price down success, stock_code={}, reminder_price={}', strategy_config.stock_code,
                               reminder_price)
            else:
                logger.error('set price down error:{}', ask_data)

    else:
        logger.error('set price up error:{}', ask_data)


def reset_price_monitor(stock_code):
    """
    重置监控的实时报价
    :param stock_code: 股票代码
    :return:
    """
    strategy_config = stock_strategy_config.query_strategy_config(stock_code, Strategy.GRID)

    grid_config = grid_strategy_config.query_strategy_config(strategy_config.id)

    code = strategy_config.stock_code
    price_info = {}

    if strategy_config.remaining_buy_quantity > 0:
        buy_price = calculate_amplitude_price(grid_config.base_price, grid_config, False)
        price_info['buy_price'] = buy_price

    if strategy_config.remaining_sell_quantity > 0:
        sell_price = calculate_amplitude_price(grid_config.base_price, grid_config, True)
        price_info['sell_price'] = sell_price

    monitor_code_dict[code] = price_info


def subscribe_quote(stocks: list):
    quote_ctx = FutuContext.instance().get_quote_context()
    quote_ctx.set_handler(StockQuoteListen())

    stock_code_list = []
    for strategy_config in stocks:
        stock_code_list.append(strategy_config.market + '.' + strategy_config.stock_code)

    ret_code, data = quote_ctx.subscribe(stock_code_list, [futu.SubType.QUOTE])
    if ret_code != futu.RET_OK:
        logger.error('subscribe quote error:{}', data)
        return

    for strategy_config in stocks:
        reset_price_monitor(strategy_config.stock_code)


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
    subject.subscribe(StockMarket.US, GridObserver())
    strategy_config_list = stock_strategy_config.query_all_config(Strategy.GRID)

    if strategy_config_list is not None:
        if has_longbridge(strategy_config_list):
            LongbridgeContext.instance().get_trade_context().set_on_order_changed(on_order_changed)
            LongbridgeContext.instance().get_trade_context().subscribe([lb.TopicType.Private])
            print('set longbridge success')

        if has_futu_us(strategy_config_list):
            FutuContext.instance().get_trade_context(StockMarket.US).set_handler(TradeOrderHandler())
            print('set futu us success')

        if has_futu_hk(strategy_config_list):
            FutuContext.instance().get_trade_context(StockMarket.HK).set_handler(TradeOrderHandler())
            print('set futu hk success')

        FutuContext.instance().get_quote_context().set_handler(PriceReminder())

    stock_hk = []
    for strategy_config in strategy_config_list:
        if strategy_config.market == StockMarket.US.value:
            reset_price_reminder(strategy_config.stock_code)
        else:
            stock_hk.append(strategy_config)

    if len(stock_hk) > 0:
        subscribe_quote(stock_hk)

    print(monitor_code_dict)
    print('price_reminder start success...')
