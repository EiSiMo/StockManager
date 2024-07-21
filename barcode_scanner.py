import threading
import time
import logging

logger = logging.getLogger("Root")


class BarcodeScanner(threading.Thread):
    def __init__(self, barcode_queue, saying_queue):
        super().__init__()
        self.barcode_queue = barcode_queue
        self.saying_queue = saying_queue
        self.running = True

    def run(self):
        while self.running:
            try:
                barcode = self.scan_barcode()
                self.barcode_queue.put(barcode)
            except Exception as e:
                logger.error("Exception in BarcodeScanner thread", exc_info=e)
                self.running = False

    def scan_barcode(self):
        hid = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l',
               16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w',
               27: 'x', 28: 'y', 29: 'z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8',
               38: '9', 39: '0', 44: ' ', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~',
               54: ',', 55: '.', 56: '/'}
        hid2 = {4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J', 14: 'K', 15: 'L',
                16: 'M', 17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S', 23: 'T', 24: 'U', 25: 'V', 26: 'W',
                27: 'X', 28: 'Y', 29: 'Z', 30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*',
                38: '(', 39: ')', 44: ' ', 45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~',
                54: '<', 55: '>', 56: '?'}
        fp = open("/dev/hidraw0", "rb")
        ss = ""
        shift = False
        done = False
        while not done:
            buffer = fp.read(8)
            for c in buffer:
                if c > 0:
                    if int(c) == 40:
                        done = True
                        break
                    if shift:
                        if int(c) == 2:
                            shift = True
                        else:
                            ss += hid2[int(c)]
                            shift = False
                    else:
                        if int(c) == 2:
                            shift = True
                        else:
                            ss += hid[int(c)]
        return ss

