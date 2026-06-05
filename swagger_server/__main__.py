#!/usr/bin/env python3

import connexion
from flask.json.provider import DefaultJSONProvider

from swagger_server import encoder


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        return encoder.JSONEncoder().default(o)


def main():
    app = connexion.App(__name__, specification_dir='./swagger/')
    app.app.json = CustomJSONProvider(app.app)
    app.add_api('swagger.yaml', arguments={'title': 'RAG API Service'}, pythonic_params=True)
    app.run(port=5000)


if __name__ == '__main__':
    main()
