import logging.config


def configure_logging(*, debug: bool) -> None:
    """Configure timestamped logging for the app and for uvicorn's own loggers.

    Runs at module-import time (before `Server.run()` starts serving), which is
    after uvicorn's own `Config.configure_logging()` call — so this config wins
    and stays in effect for the lifetime of the process.
    """
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": "DEBUG" if debug else "INFO",
            },
            "loggers": {
                "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
                "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
                "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
                "httpcore": {"handlers": ["console"], "level": "WARNING", "propagate": False},
            },
        }
    )
