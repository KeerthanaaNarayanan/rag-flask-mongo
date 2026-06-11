#!/usr/bin/env python3

import logging
import os

import connexion
from flask.json.provider import DefaultJSONProvider

from swagger_server import encoder


def configure_logging() -> None:
    debug_mode = os.getenv("DEBUG_MODE", "false").strip().lower() in {"1", "true", "yes"}
    level = logging.DEBUG if debug_mode else logging.INFO

    # Silence everything from third-party libraries at root level.
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Only our service loggers get the configured level.
    service_logger = logging.getLogger("swagger_server")
    service_logger.setLevel(level)
    if not service_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        service_logger.addHandler(handler)

    service_logger.info("Logging configured — level=%s", "DEBUG" if debug_mode else "INFO")


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, o):
        return encoder.JSONEncoder().default(o)


def create_app() -> connexion.App:
    app = connexion.App(__name__, specification_dir='./swagger/')
    app.app.json = CustomJSONProvider(app.app)
    app.add_api('swagger.yaml', arguments={'title': 'RAG API Service'}, pythonic_params=True)
    return app


def main():
    configure_logging()
    app = create_app()
    app.run(port=5000)


if __name__ == '__main__':
    main()
