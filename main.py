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

from flask import Flask, render_template, Response, request
from todoist_api_python.api import TodoistAPI
from gtts import gTTS

# TODO make logger log unexpected crashes!
# TODO intensive testing
timed_handler = logging.handlers.TimedRotatingFileHandler(
    "logs/log.log",
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf8"
)
timed_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(name)s %(levelname)s: %(message)s")
timed_handler.setFormatter(formatter)


class ProductDatabase(dict):
    def __init__(self, filename, *args, **kwargs):
        super(ProductDatabase, self).__init__(*args, **kwargs)

        self.logger = logging.getLogger("\t\tDatabase")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(timed_handler)

        self.filename = filename

        self.logger.log(logging.DEBUG, "initializing database")

        db_validation_regex = re.compile(r"^$|^(.+: (\d+, )*\d+\n)+$")

        if os.path.exists(filename):
            self.logger.log(logging.DEBUG, f"reading db file '{filename}'")
            with open(filename, "r", encoding="utf8") as file:
                text = file.read()
                self.logger.log(logging.DEBUG, f"{len(text)} characters read")
                self.logger.log(logging.DEBUG, "testing data validity")
                if re.fullmatch(db_validation_regex, text):
                    self.logger.log(logging.DEBUG, "data valid")
                    self.logger.log(logging.DEBUG, "loading data")
                    for line in text.splitlines(keepends=False):
                        line = line.split(": ")
                        name = line[0]
                        codes = line[1].split(", ")
                        self.__setitem__(name, codes, sort_and_save=False)
                    self.logger.log(logging.DEBUG, "data loaded")
                    self._save()
                else:
                    self.logger.log(logging.CRITICAL, "Database file has wrong formatting")
                    raise Exception("Invalid database format")
        else:
            open(filename, "a").close()

        self.logger.log(logging.INFO, "database initialised")

    def __setitem__(self, name, codes, save=True):
        self.logger.log(logging.DEBUG, f"__setitem__({name}, {codes}, save={save}) called")
        if isinstance(codes, str):
            codes = [codes]

        if name in self.keys():
            codes.extend(self.__getitem__(name))

        super(ProductDatabase, self).__setitem__(name, codes)

        if save:
            self._save()

    def __delitem__(self, name_or_code):
        self.logger.log(logging.DEBUG, f"__delitem__({name_or_code}) called")
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
        self.logger.log(logging.DEBUG, f"__len__ called")
        count = 0
        for codes in self.values():
            count += len(codes)
        self.logger.log(logging.DEBUG, f"{count} codes counted")
        return count

    def _save(self):
        self.logger.log(logging.DEBUG, f"_save called")
        self._sort()
        result = str()
        for name, codes in self.items():
            result += f"{name}: {', '.join(codes)}\n"

        with open(self.filename, "w", encoding="utf8") as file:
            file.write(result)

    def _sort(self):
        self.logger.log(logging.DEBUG, "_sort called")
        sorted_items = sorted(self.items(), key=lambda s: s[0].lower())
        self.clear()
        self.update(sorted_items)

    def find(self, code):
        self.logger.log(logging.DEBUG, f"find({code}) called")
        for index, (name, codes) in enumerate(self.items()):
            if code in codes:
                self.logger.log(logging.DEBUG, f"code '{code}' found in line {index+1}")
                return name
        self.logger.log(logging.DEBUG, f"code '{code}' not found in database")
        return None


class StockManager:
    def __init__(self):
        self.logger = logging.getLogger("SManager")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(timed_handler)

        self.logger.log(logging.DEBUG, f"initializing StockManager")

        self.todoist_api_key = "5e3904e04bede42252be34b19d88a401240d6dc0"
        self.todoist_project_id = "2336429901"

        self.product_database = ProductDatabase("product_database.txt")

        self.codes_todo = ["000000000"]

        pygame.mixer.init()

        self.logger.log(logging.INFO, f"StockManager initialized ")

    def say(self, text):
        self.logger.log(logging.INFO, f"say({text}) called")
        pygame.mixer.init()
        tts = gTTS(text, lang="de", slow=False)
        self.logger.log(logging.DEBUG, f"gTTS audio generated")
        audio_stream = io.BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        pygame.mixer.music.load(audio_stream, "mp3")
        self.logger.log(logging.DEBUG, f"playing audio")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        self.logger.log(logging.DEBUG, f"playing audio completed")

    def scan_barcode(self):
        self.logger.log(logging.INFO, f"scan_barcode() called")
        vid = cv2.VideoCapture(0)
        self.logger.log(logging.DEBUG, f"video capture created - starting frame loop")
        while True:
            ret, frame = vid.read()
            if ret:
                result = pyzbar.pyzbar.decode(frame)
                if result:
                    code = result[0].data.decode("utf8")
                    if len(code) > 6:
                        self.logger.log(logging.INFO, f"barcode found '{code}' - length ok - returning")
                        vid.release()
                        return code
                    else:
                        self.logger.log(logging.DEBUG, f"barcode found '{code}' but too short to process (<6)")
            else:
                self.logger.log(logging.WARNING, f"invalid frame - restarting camera")
                vid.release()
                vid = cv2.VideoCapture(0)

    def add_item_to_todoist(self, name):
        self.logger.log(logging.INFO, f"add_item_to_todoist({name}) called")
        has_quantifier_regex = re.compile(r"^\d+x .+$")
        self.logger.log(logging.DEBUG, f"initializing Todoist API")
        api = TodoistAPI(self.todoist_api_key)
        already = False
        self.logger.log(logging.DEBUG, f"retrieving current shopping list from todoist")
        tasks = [task for task in api.get_tasks() if task.project_id == self.todoist_project_id]

        self.logger.log(logging.DEBUG, f"checking if '{name}' is already on the list")
        for task in tasks:
            if task.content.endswith(name):
                self.logger.log(logging.INFO, f"'{name}' is already on list - adding or increasing quantifier")
                already = True
                if re.search(has_quantifier_regex, task.content):
                    quantifier = int(task.content.split("x")[0])
                    self.logger.log(logging.DEBUG, f"increasing quantifier to {quantifier + 1}")
                    api.update_task(task_id=task.id,
                                    content=str(quantifier + 1) + "x" + task.content.split("x")[1])
                else:
                    self.logger.log(logging.DEBUG, f"adding 2x quantifier")
                    api.update_task(task_id=task.id, content=f"2x {name}")

        if not already:
            self.logger.log(logging.INFO, f"'{name}' is not on on the list - adding it")
            api.add_task(content=name, project_id=self.todoist_project_id)

    def run(self):
        self.logger.log(logging.DEBUG, f"run() called")
        self.say("Vorratsmanager gestartet.")
        self.logger.log(logging.INFO, f"starting main loop")
        while True:
            code = self.scan_barcode()
            self.say("Code erkannt.")
            self.logger.log(logging.INFO, f"barcode '{code}' detected")

            self.logger.log(logging.DEBUG, f"searching barcode in database")
            product_name = self.product_database.find(code)

            if product_name:
                self.logger.log(logging.INFO, f"barcode already in database")
                self.say(f"Ich schreibe {product_name} auf deine Einkaufsliste.")
                self.logger.log(logging.DEBUG, f"adding item to shopping list")
                self.add_item_to_todoist(product_name)
            else:
                self.logger.log(logging.INFO, f"barcode not in database yet")
                if code not in self.codes_todo:
                    self.logger.log(logging.DEBUG, f"adding item to todo list")
                    self.codes_todo.append(code)
                    self.say("Unbekanntes Produkt. Bitte in der Datenbank ergänzen!")
                else:
                    self.logger.log(logging.DEBUG, f"item already on todo list")
                    self.say("Bitte öffne die Webseite, um das Produkt zu indizieren.")


class WebInterface:
    def __init__(self, manager):
        self.logger = logging.getLogger("WebIface")
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(timed_handler)

        self.logger.log(logging.DEBUG, f"initializing WebInterface")

        self.manager = manager
        self.app = Flask(__name__)
        self.setup_routes()

        self.logger.log(logging.INFO, f"WebInterface initialized")

    def generate_entries(self):
        self.logger.log(logging.DEBUG, f"generate_entries() called")
        result = ""
        self.logger.log(logging.DEBUG, f"generating {len(self.manager.product_database.keys())} scrollbox items")
        for name in self.manager.product_database.keys():
            result += f"<div class='item'>{name}</div>\n"
        return result

    def setup_routes(self):
        self.logger.log(logging.INFO, f"setup_routes() called")
        self.logger.log(logging.DEBUG, f"setting up flask routes")

        @self.app.route("/")
        def home():
            self.logger.log(logging.INFO, f"flask route '/' called")
            self.logger.log(logging.DEBUG, f"waiting 0.1s to make sure the database has finished saving changes")
            time.sleep(0.1)
            self.logger.log(logging.DEBUG, f"fetching next one from the todo list")
            code = next(iter(self.manager.codes_todo), None)
            if not code:
                self.logger.log(logging.DEBUG, f"todo list is empty")
                code = "Aktuell keine zu indizierenden Produkte"
            self.logger.log(logging.INFO, f"sending response 200 OK")
            return render_template("index.html", entries=self.generate_entries(), code=code)

        @self.app.route("/new", methods=["POST"])
        def new():
            self.logger.log(logging.INFO, f"flask route '/new' called")
            name = request.json["name"]
            code = request.json["code"]

            self.logger.log(logging.DEBUG, f"removing code '{code}' from todo list")
            if code in self.manager.codes_todo:
                self.manager.codes_todo.remove(code)

            self.logger.log(logging.INFO, f"adding {name} and {code} to the database")
            self.manager.product_database[name] = code

            self.logger.log(logging.INFO, f"sending response 200 OK")
            return Response("{}", status=200, mimetype="application/json")

        @self.app.route("/discard", methods=["POST"])
        def discard():
            self.logger.log(logging.INFO, f"flask route '/discard' called")
            code = request.json["code"]
            self.logger.log(logging.DEBUG, f"removing code '{code}' from todo list")
            if code in self.manager.codes_todo:
                self.manager.codes_todo.remove(code)
            self.logger.log(logging.INFO, f"sending response 200 OK")
            return Response("{}", status=200, mimetype="application/json")

    def run(self, host="0.0.0.0", port=80):
        self.logger.log(logging.INFO, f"run(host={host}, port={port}) called")
        self.logger.log(logging.INFO, f"starting flask server")
        self.app.run(host=host, port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    manager = StockManager()
    manager_thread = threading.Thread(target=manager.run)
    manager_thread.start()

    interface = WebInterface(manager)
    interface.run()

    manager_thread.join()
