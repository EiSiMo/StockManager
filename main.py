import pygame
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


class ProductDatabase(dict):
    def __init__(self, filename, *args, **kwargs):
        super(ProductDatabase, self).__init__(*args, **kwargs)

        self.filename = filename

        db_validation_regex = re.compile(r"^$|^(.+: (\d+, )*\d+\n)+$")

        if os.path.exists(filename):
            with open(filename, "r", encoding="utf8") as file:
                text = file.read()
                if re.fullmatch(db_validation_regex, text):
                    for line in text.splitlines(keepends=False):
                        line = line.split(": ")
                        name = line[0]
                        codes = line[1].split(", ")
                        self.__setitem__(name, codes, save=False)
                    self._save()
                else:
                    raise Exception("Invalid database format")
        else:
            open(filename, "a").close()

    def __setitem__(self, name, codes, save=True):
        if isinstance(codes, str):
            codes = [codes]

        if name in self.keys():
            codes.extend(self.__getitem__(name))

        super(ProductDatabase, self).__setitem__(name, codes)

        self._sort()
        if save:
            self._save()

    def __delitem__(self, name_or_code):
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
        count = 0
        for codes in self.values():
            count += len(codes)
        return count

    def _save(self):
        result = str()
        for name, codes in self.items():
            result += f"{name}: {', '.join(codes)}\n"

        with open(self.filename, "w", encoding="utf8") as file:
            file.write(result)

    def _sort(self):
        sorted_items = sorted(self.items(), key=lambda s: s[0].lower())
        self.clear()
        self.update(sorted_items)

    def find(self, code):
        for name, codes in self.items():
            if code in codes:
                return name
        return None


class StockManager:
    def __init__(self):
        self.todoist_api_key = "5e3904e04bede42252be34b19d88a401240d6dc0"
        self.todoist_project_id = "2336429901"

        self.product_database = ProductDatabase("product_database.txt")
        self.codes_todo = ["000000000"]

        pygame.mixer.init()

    def say(self, text):
        pygame.mixer.init()
        tts = gTTS(text, lang="de", slow=False)
        audio_stream = io.BytesIO()
        tts.write_to_fp(audio_stream)
        audio_stream.seek(0)
        pygame.mixer.music.load(audio_stream, "mp3")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    def scan_barcode(self):
        vid = cv2.VideoCapture(0)
        while True:
            ret, frame = vid.read()
            if ret:
                result = pyzbar.pyzbar.decode(frame)
                if result:
                    code = result[0].data.decode("utf8")
                    if len(code) > 6:
                        vid.release()
                        return code
            else:
                vid.release()
                vid = cv2.VideoCapture(0)

    def add_item_to_todoist(self, item_name):
        has_quantifier_regex = re.compile(r"^\d+x .+$")
        api = TodoistAPI(self.todoist_api_key)
        already = False
        tasks = [task for task in api.get_tasks() if task.project_id == self.todoist_project_id]

        for task in tasks:
            if task.content.endswith(item_name):
                already = True
                if re.search(has_quantifier_regex, task.content):
                    api.update_task(task_id=task.id,
                                    content=str(int(task.content.split("x")[0]) + 1) + "x" + task.content.split("x")[1])
                else:
                    api.update_task(task_id=task.id, content=f"2x {item_name}")

        if not already:
            api.add_task(content=item_name, project_id=self.todoist_project_id)

    def run(self):
        self.say("Vorratsmanager gestartet.")
        while True:
            code = self.scan_barcode()
            self.say("Code erkannt.")

            product_name = self.product_database.find(code)

            if product_name:
                self.say(f"Ich schreibe {product_name} auf deine Einkaufsliste.")
                self.add_item_to_todoist(product_name)
            else:
                if code not in self.codes_todo:
                    self.codes_todo.append(code)
                    self.say("Unbekanntes Produkt. Bitte in der Datenbank ergänzen!")
                else:
                    self.say("Bitte öffne die Webseite, um das Produkt zu indizieren.")


class WebInterface:
    def __init__(self, manager):
        self.manager = manager
        self.app = Flask(__name__)
        self.setup_routes()

    def generate_entries(self):
        result = ""
        for name in self.manager.product_database.keys():
            result += f"<div class='item'>{name}</div>\n"
        return result

    def setup_routes(self):
        @self.app.route('/')
        def home():
            time.sleep(0.1)
            code = next(iter(self.manager.codes_todo), None)
            if not code:
                code = "Aktuell keine zu indizierenden Produkte"
            return render_template("index.html", entries=self.generate_entries(), code=code)

        @self.app.route("/new", methods=["POST"])
        def new():
            name = request.json["name"]
            code = request.json["code"]
            if code in self.manager.codes_todo:
                self.manager.codes_todo.remove(code)

            self.manager.product_database[name] = code

            return Response("{}", status=200, mimetype="application/json")

        @self.app.route("/discard", methods=["POST"])
        def discard():
            code = request.json["code"]
            if code in self.manager.codes_todo:
                self.manager.codes_todo.remove(code)
            return Response("{}", status=200, mimetype="application/json")

    def run(self, host="0.0.0.0", port=80):
        self.app.run(host=host, port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    manager = StockManager()
    manager_thread = threading.Thread(target=manager.run)
    manager_thread.start()

    interface = WebInterface(manager)
    interface.run()

    manager_thread.join()
