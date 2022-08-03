from flask import Flask
from src.strategy import price_remaining

price_remaining.init()
app = Flask(__name__)


@app.route('/')
def hello_world():  # put application's code here
    return 'Hello World!'


if __name__ == '__main__':
    app.run()
