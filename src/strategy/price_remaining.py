from src.db.stock_strategy_config import StockStrategyConfig
from src.strategy.base_strategy import *


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
            logging.info('no strategy config, stock_code={}, strategy={}', stock_code, Strategy.GRID)
            return

        price = content['price']
        side = StockOrderSide.SELL if content['reminder_type'] == 'PRICE_UP' else StockOrderSide.BUY
        success = LongbridgeOrder().order(stock_code, Strategy.GRID, Decimal(price), side)

        if not success:
            reset_price_reminder(strategy_config)


def reset_price_reminder(strategy_config: StockStrategyConfig) -> None:
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
        if grid_config.remaining_sell_quantity > 0:
            reminder_price = calculate_amplitude_price(strategy_config, grid_config, True)
            ret_ask, ask_data = quote_ctx.set_price_reminder(code=code,
                                                             op=SetPriceReminderOp.ADD,
                                                             reminder_type=PriceReminderType.PRICE_UP,
                                                             reminder_freq=PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == RET_OK:
                logger.info('set price up success, stock_code={}, reminder_price={}', strategy_config.stock_code,
                            grid_config.reminder_price)
            else:
                logger.error('error:{}', ask_data)

        # set price down
        if grid_config.remaining_buy_quantity > 0:
            reminder_price = calculate_amplitude_price(grid_config.base_price, grid_config, False)

            ret_ask, ask_data = quote_ctx.set_price_reminder(code,
                                                             op=SetPriceReminderOp.ADD,
                                                             reminder_type=PriceReminderType.PRICE_DOWN,
                                                             reminder_freq=PriceReminderFreq.ONCE,
                                                             value=reminder_price)
            if ret_ask == RET_OK:
                logger.info('set price down success, stock_code={}, reminder_price={}', strategy_config.stock_code,
                            grid_config.reminder_price)
            else:
                logger.error('set price down error:{}', ask_data)

    else:
        logger.error('set price up error:{}', ask_data)
