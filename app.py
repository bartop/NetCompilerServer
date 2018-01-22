from flask import Flask

from flask_restful import Api

app = Flask(__name__)

rest_api = Api(app)
