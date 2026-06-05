import logging

import connexion
from flask_testing import TestCase
from flask.json.provider import DefaultJSONProvider

from swagger_server.encoder import JSONEncoder


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        return JSONEncoder().default(o)


class BaseTestCase(TestCase):

    def create_app(self):
        logging.getLogger('connexion.operation').setLevel('ERROR')
        app = connexion.App(__name__, specification_dir='../swagger/')
        app.app.json = CustomJSONProvider(app.app)
        app.add_api('swagger.yaml')
        return app.app
