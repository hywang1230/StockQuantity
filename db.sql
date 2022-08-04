create table longbridge_auth
(
    id                 int auto_increment comment '主键'
        primary key,
    app_key            varchar(128)                        not null comment 'APP KEY',
    app_secret         varchar(128)                        not null comment 'APP SECRET',
    access_token       varchar(1024)                       not null comment 'ACCESS TOKEN',
    token_expired_time timestamp                           not null comment 'token过期时间',
    gmt_create         timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    gmt_modified       timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '修改时间'
)
    comment '长桥鉴权信息';

create table stock_strategy_config
(
    id                      int auto_increment comment '主键'
        primary key,
    stock_code              varchar(16)                         not null comment '股票代码',
    market                  char(2)                             not null comment '市场：US.美股，HK.港股',
    strategy                varchar(16)                         not null comment '策略',
    single_sell_quantity    int                                 not null comment '单次卖出数量',
    single_buy_quantity     int                                 not null comment '单次买入数量',
    remaining_sell_quantity int                                 not null comment '剩余可卖出数量',
    remaining_buy_quantity  int                                 not null comment '剩余可买入数量',
    order_account           int       default 2                 not null comment '下单账号：1.富途，2.长桥',
    gmt_create              timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    gmt_modified            timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '修改时间',
    constraint uq_stock_code_strategy
        unique (stock_code, strategy)
)
    comment '策略配置';

create table grid_strategy_config
(
    id                int auto_increment comment '主键'
        primary key,
    stock_strategy_id int                                 not null comment '策略配置ID',
    base_price        decimal(20, 8)                      not null comment '基础价，币种为对应市场的币种',
    rise_amplitude    decimal(20, 8)                      not null comment '上升幅度',
    fall_amplitude    decimal(20, 8)                      null comment '下跌幅度',
    amplitude_type    int       default 1                 not null comment '幅度类型：1.百分比，2.价格',
    gmt_create        timestamp default CURRENT_TIMESTAMP not null comment '创建时间',
    gmt_modified      timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '修改时间',
    constraint uq_stock_strategy_id
        unique (stock_strategy_id)
)
    comment '网格策略配置';


create table trade_order_record
(
    id           int auto_increment comment '主键'
        primary key,
    stock_code   varchar(16)                              not null comment '股票代码',
    market       char(2)                                  not null comment '市场：US.美股，HK.港股',
    strategy     varchar(16)                              not null comment '策略',
    order_id     varchar(32)                              not null comment '订单号',
    price        decimal(20, 8)                           not null comment '价格，币种为对应市场的币种',
    quantity     int                                      null comment '数量',
    side         int                                      null comment '方向：1.sell，2.buy',
    order_time   timestamp                                not null comment '下单时间',
    status       int            default 0                 not null comment '状态：0.交易中，1.成功，2.失败，3.撤单',
    fee          decimal(20, 8) default 0.00000000        null comment '费用，币种为对应市场的币种',
    finish_time  timestamp                                null comment '结束时间，即成交时间或撤单时间',
    gmt_create   timestamp      default CURRENT_TIMESTAMP not null comment '创建时间',
    gmt_modified timestamp      default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP comment '修改时间',
    constraint uq_order_id
        unique (order_id)
)
    comment '交易订单记录';