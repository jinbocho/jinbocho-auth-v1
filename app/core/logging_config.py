import logging.config


def configure_logging(*, debug: bool, otel_enabled: bool = False) -> None:
    """Configure timestamped logging for the app and for uvicorn's own loggers.

    Runs at module-import time (before `Server.run()` starts serving), which is
    after uvicorn's own `Config.configure_logging()` call — so this config wins
    and stays in effect for the lifetime of the process.

    otel_enabled adds trace_id/span_id to the format string, for correlating
    log lines with Tempo traces in Grafana. Callers must call
    telemetry.instrument_logging() before this function when otel_enabled is
    true — it patches every LogRecord to carry those fields — otherwise the
    first log call raises (the field would be referenced but never populated).
    """
    default_format = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    if otel_enabled:
        default_format = (
            "%(asctime)s %(levelname)-8s [%(name)s] "
            "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(message)s"
        )

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": default_format,
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
