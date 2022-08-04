from src.db.base import *


class LongbridgeAuth(BaseModel):
    app_key = CharField()
    app_secret = CharField()
    access_token = CharField()
    token_expired_time = DateField()
    gmt_create = DateTimeField(constraints=[SQL("DEFAULT current_timestamp()")])
    gmt_modified = DateTimeField(constraints=[SQL("DEFAULT current_timestamp()")])

    class Meta:
        table_name = 'longbridge_auth'


def get_auth() -> LongbridgeAuth:
    auths = LongbridgeAuth.select()
    if auths is not None:
        return auths[0]
    else:
        logger.info('no auth info')


def update_token(token, token_expired_time):
    LongbridgeAuth.update(access_token=token, token_expired_time=token_expired_time).execute()

