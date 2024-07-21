import logging
import queue
import time
import sys

from stock_manager import StockManager
from barcode_scanner import BarcodeScanner
from web_interface import WebInterface
from speaker import Speaker
from logging_setup import setup_logging

logger = logging.getLogger("Root")


def main():
    setup_logging()

    barcode_queue = queue.Queue()
    saying_queue = queue.Queue()

    manager = StockManager(barcode_queue, saying_queue)
    scanner = BarcodeScanner(barcode_queue, saying_queue)
    interface = WebInterface(manager)
    speaker = Speaker(saying_queue)

    threads = [manager, scanner, interface, speaker]

    for thread in threads:
        thread.start()

    while all(thread.running for thread in threads):
        time.sleep(1)

    for thread in threads:
        thread.running = False

    for thread in threads:
        thread.join()

    logger.info("All threads have been stopped. Exiting program.")
    sys.exit(1)


if __name__ == "__main__":
    main()