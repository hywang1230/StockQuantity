import configparser
import os

ROOT_DIR = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))

config = configparser.ConfigParser()
config.read(ROOT_DIR + '/application.ini')


class DbConfiguration:
    def __init__(self) -> None:
        db_dict = dict(config.items('db'))
        self.host = db_dict['host']
        self.port = int(db_dict['port'])
        self.user = db_dict['user']
        self.password = db_dict['password']
        self.database = db_dict['database']


class FutuConfiguration:

    def __init__(self) -> None:
        futu_dict = dict(config.items('futu'))
        self.host = futu_dict['host']
        self.port = int(futu_dict['port'])
        self.unlock_password_md5 = futu_dict['unlock_password_md5']


class TgConfiguration:

    def __init__(self) -> None:
        tg_dict = dict(config.items('tg'))
        self.api_token = tg_dict['api_token']
        self.chat_id = int(tg_dict['chat_id'])
