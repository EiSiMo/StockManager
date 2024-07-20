import pygame
import logging
import logging.handlers
import io
import os.path
import pyzbar.pyzbar
import cv2
import threading
import re
import time
import pygments
import pygments.lexers
import pygments.formatters
import sys

from flask import Flask, render_template, Response, request, send_from_directory
from todoist_api_python.api import TodoistAPI
from gtts import gTTS

# TODO hiding api keys, find out how to delete them in past commit, publish repo

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


def log_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = log_exception


class LoggingThread(threading.Thread):
    def run(self):
        try:
            if self._target:
                self._target(*self._args, **self._kwargs)
        except Exception as e:
            logger.error("Exception in thread", exc_info=e)


class ProductDatabase(dict):
    def __init__(self, filename, *args, **kwargs):
        super(ProductDatabase, self).__init__(*args, **kwargs)

        self.filename = filename

        logger.debug("initializing database")

        db_validation_regex = re.compile(r"^$|^(.+: (\d+, )*\d+\n)+$")

        if os.path.exists(filename):
            logger.debug(f"reading db file '{filename}'")
            with open(filename, "r", encoding="utf8") as file:
                text = file.read()
                logger.debug(f"{len(text)} characters read")
                logger.debug("testing data validity")
                if re.fullmatch(db_validation_regex, text):
                    logger.debug("data valid")
                    logger.debug("loading data")
                    for line in text.splitlines(keepends=False):
                        line = line.split(": ")
                        name = line[0]
                        codes = line[1].split(", ")
                        self.__setitem__(name, codes, save=False, log=False)
                    logger.debug("data loaded")
                    self._save()
                else:
                    logger.critical("Database file has wrong formatting")
                    raise Exception("Invalid database format")
        else:
            open(filename, "a").close()

        logger.info("database initialised")

    def __setitem__(self, name, codes, save=True, log=True):
        if log:
            logger.debug(f"__setitem__({name}, {codes}, save={save}) called")
        if isinstance(codes, str):
            codes = [codes]

        if name in self.keys():
            codes.extend(self.__getitem__(name))

        super(ProductDatabase, self).__setitem__(name, codes)

        if save:
            self._save()

    def __delitem__(self, name_or_code):
        logger.debug(f"__delitem__({name_or_code}) called")
        if name_or_code in self.keys():
            super(ProductDatabase, self).__delitem__(name_or_code)
            self._save()
        else:
            for name, codes in self.items():
                if name_or_code in codes:
                    codes.remove(name_or_code)
                    super(ProductDatabase, self).__setitem__(name, codes)
                    self._save()

    def __len__(self):
        logger.debug(f"__len__() called")
        count = 0
        for codes in self.values():
            count += len(codes)
        return count

    def _save(self):
        logger.debug(f"_save() called")
        self._sort()
        result = str()
        for name, codes in self.items():
            result += f"{name}: {', '.join(codes)}\n"

        with open(self.filename, "w", encoding="utf8") as file:
            file.write(result)

    def _sort(self):
        logger.debug("_sort() called")
        sorted_items = sorted(self.items(), key=lambda s: s[0].lower())
        self.clear()
        self.update(sorted_items)

    def find(self, code):
        logger.debug(f"find({code}) called")
        for index, (name, codes) in enumerate(self.items()):
            if code in codes:
                logger.debug(f"code '{code}' found in line {index+1}")
                return name
        logger.debug(f"code '{code}' not found in database")
        return None


class StockManager:
    def __init__(self):
        logger.debug(f"initializing StockManager")

        self.todoist_api_key = "5e3904e04bede42252be34b19d88a401240d6dc0"
        self.todoist_project_id = "2336429901"

        self.product_database = ProductDatabase("product_database.txt")

        self.codes_todo = ["000000000"]

        pygame.mixer.init()

        logger.info(f"StockManager initialized")

    def say(self, text):
        logger.info(f"say({text}) called")
        pygame.mixer.init()
        tts = gTTS(text, lang="de", slow=False)
        logger.debug(f"gTTS audio generated")
        audio_stream = io.BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        pygame.mixer.music.load(audio_stream, "mp3")
        logger.debug(f"playing audio")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        logger.debug(f"playing audio completed")

    def scan_barcode_cam(self):
        """for use with a camera"""
        logger.info(f"scan_barcode_cam() called")
        vid = cv2.VideoCapture(0)
        logger.debug(f"video capture created - starting frame loop")
        while True:
            ret, frame = vid.read()
            if ret:
                result = pyzbar.pyzbar.decode(frame)
                if result:
                    code = result[0].data.decode("utf8")
                    if len(code) > 6:
                        logger.info(f"barcode found '{code}' - length ok - returning")
                        vid.release()
                        return code
                    else:
                        logger.debug(f"barcode found '{code}' but too short to process (<6)")
            else:
                logger.warning(f"invalid frame - restarting camera")
                vid.release()
                vid = cv2.VideoCapture(0)

    def scan_barcode(self):
        """for use with a barcode scanner"""
        logger.info(f"scan_barcode() called")
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
        fp = open('/dev/hidraw0', 'rb')
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

    def add_item_to_todoist(self, name):
        logger.info(f"add_item_to_todoist({name}) called")
        has_quantifier_regex = re.compile(r"^\d+x .+$")
        logger.debug(f"initializing Todoist API")
        api = TodoistAPI(self.todoist_api_key)
        already = False
        logger.debug(f"retrieving current shopping list from todoist")
        tasks = [task for task in api.get_tasks() if task.project_id == self.todoist_project_id]

        logger.debug(f"checking if '{name}' is already on the list")
        for task in tasks:
            if task.content.endswith(name):
                logger.info(f"'{name}' is already on list - adding or increasing quantifier")
                already = True
                if re.search(has_quantifier_regex, task.content):
                    quantifier = int(task.content.split("x")[0])
                    logger.debug(f"increasing quantifier to {quantifier + 1}")
                    api.update_task(task_id=task.id,
                                    content=str(quantifier + 1) + "x" + task.content.split("x")[1])
                else:
                    logger.debug(f"adding 2x quantifier")
                    api.update_task(task_id=task.id, content=f"2x {name}")

        if not already:
            logger.info(f"'{name}' is not on on the list - adding it")
            api.add_task(content=name, project_id=self.todoist_project_id)

    def run(self):
        logger.info(f"run() called")
        self.say("Vorratsmanager gestartet.")
        logger.info(f"starting main loop")
        while True:
            time.sleep(100)
            code = self.scan_barcode()
            self.say("Code erkannt.")
            logger.info(f"barcode '{code}' detected")

            logger.debug(f"searching barcode in database")
            product_name = self.product_database.find(code)

            if product_name:
                logger.info(f"barcode already in database")
                self.say(f"Ich schreibe {product_name} auf deine Einkaufsliste.")
                logger.info(f"adding item to shopping list")
                self.add_item_to_todoist(product_name)
            else:
                logger.info(f"barcode not in database yet")
                if code not in self.codes_todo:
                    logger.debug(f"adding item to todo list")
                    self.codes_todo.append(code)
                    self.say("Unbekanntes Produkt. Bitte in der Datenbank ergänzen!")
                else:
                    logger.debug(f"item already on todo list")
                    self.say("Bitte öffne die Webseite, um das Produkt zu indizieren.")


class WebInterface:
    def __init__(self, manager):
        logger.info(f"initializing WebInterface")

        self.manager = manager
        self.app = Flask(__name__)
        self.setup_routes()

        # disable flask console logging
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        null_handler = logging.NullHandler()
        logging.getLogger().addHandler(null_handler)

        logger.info(f"WebInterface initialized")

    def generate_entries(self):
        logger.debug(f"generate_entries() called")
        result = ""
        for name in self.manager.product_database.keys():
            result += f"<div class='item'>{name}</div>\n"
        return result

    def generate_logs(self):
        logger.debug(f"generate_logs() called")
        with open("logs/log.log", "r") as file:
            text = file.read()
        lexer = pygments.lexers.TextLexer()
        html_formatter = pygments.formatters.HtmlFormatter(style="colorful", full=True, linenos=True)

        highlighted_code = pygments.highlight(text, lexer, html_formatter)

        return highlighted_code

    def setup_routes(self):
        logger.info(f"setup_routes() called")

        @self.app.before_request
        def log_request_info():
            logger.info(f"request: {request.method} {request.path} ({request.host})")

        @self.app.route("/")
        def home():
            logger.debug(f"waiting 0.1s to make sure the database has finished saving changes")
            time.sleep(0.1)
            logger.debug(f"fetching next one from the todo list")
            code = next(iter(self.manager.codes_todo), None)
            if not code:
                logger.debug(f"todo list is empty")
                code = "Aktuell keine zu indizierenden Produkte"
            logger.info(f"sending response 200 OK")
            return render_template("index.html", entries=self.generate_entries(), code=code)

        @self.app.route("/new", methods=["POST"])
        def new():
            name = request.json["name"]
            code = request.json["code"]

            logger.debug(f"removing code '{code}' from todo list")
            if code in self.manager.codes_todo:
                self.manager.codes_todo.remove(code)

            logger.info(f"adding {name} and {code} to the database")
            self.manager.product_database[name] = code

            logger.info(f"sending response 200 OK")
            return Response("{}", status=200, mimetype="application/json")

        @self.app.route("/discard", methods=["POST"])
        def discard():
            code = request.json["code"]
            logger.debug(f"removing code '{code}' from todo list")
            if code in self.manager.codes_todo:
                self.manager.codes_todo.remove(code)
            logger.info(f"sending response 200 OK")
            return Response("{}", status=200, mimetype="application/json")

        @self.app.route("/logs")
        def logs():
            return self.generate_logs()

        @self.app.route("/favicon.ico")
        def favicon():
            return send_from_directory(os.path.join(self.app.root_path, "static/images"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.error("Unhandled exception", exc_info=(type(e), e, e.__traceback__))
            return "Internal Server Error", 500

    def run(self, host="0.0.0.0", port=80):
        logger.info(f"run(host={host}, port={port}) called")
        logger.debug(f"starting flask server")
        self.app.run(host=host, port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    manager = StockManager()
    manager_thread = LoggingThread(target=manager.run)
    manager_thread.start()

    interface = WebInterface(manager)
    interface.run()

    manager_thread.join()
