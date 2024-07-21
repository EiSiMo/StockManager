import logging
import logging.handlers
import sys


def setup_logging():
    logger = logging.getLogger("Root")
    logger.setLevel(logging.DEBUG)
    timed_handler = logging.handlers.TimedRotatingFileHandler(
        "logs/log.log",
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf8"
    )
    timed_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    timed_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)
    logger.addHandler(timed_handler)
    logger.addHandler(console_handler)
    logger.info("----- STOCKMANGER STARTED -----")

    def log_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = log_exception
