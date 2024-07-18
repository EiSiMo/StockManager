from flask import Flask, render_template, Response, request
from gtts import gTTS
import pygame
import io
import pyzbar.pyzbar
import cv2
import threading
import re
import time
from todoist_api_python.api import TodoistAPI

codes_todo = []


class StockManager:
    def __init__(self):
        self.todoist_api_key = "5e3904e04bede42252be34b19d88a401240d6dc0"
        self.todoist_project_id = "2336429901"
        self.product_database_file = "product_database.txt"
        self.initialize_pygame()

    def initialize_pygame(self):
        pygame.mixer.init()

    def load_product_database(self):
        with open(self.product_database_file, "r", encoding="utf8") as file:
            lines = file.read().strip().split('\n')
            data_dict = {}

            for line in lines:
                if ':' in line:
                    category, products_string = line.split(':')
                    category = category.strip()
                    products = [p.strip() for p in products_string.split(',')]
                    data_dict[category] = products
                else:
                    products = [p.strip() for p in line.split(',')]
                    if "Kein Produktname hinterlegt" not in data_dict:
                        data_dict["Kein Produktname hinterlegt"] = []
                    data_dict["Kein Produktname hinterlegt"].extend(products)
        return data_dict

    def order_database(self):
        with open(self.product_database_file, "r", encoding="utf8") as file:
            lines = file.readlines()
            lines.sort()
        with open(self.product_database_file, "w", encoding="utf8") as file:
            file.writelines(lines)

    def say(self, text):
        # Initialize pygame mixer
        pygame.mixer.init()

        # Generate speech using gTTS
        tts = gTTS(text, lang="de", slow=False)

        # Save the speech to an in-memory byte-stream
        audio_stream = io.BytesIO()
        tts.write_to_fp(audio_stream)

        # Move the byte-stream position to the beginning
        audio_stream.seek(0)

        # Load and play the audio from the byte-stream
        pygame.mixer.music.load(audio_stream, "mp3")
        pygame.mixer.music.play()

        # Wait until the audio finishes playing
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

    def add_item_to_einkaufsliste(self, item_name):
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

    def start(self):
        self.order_database()
        self.say("Vorratsmanager gestartet.")
        while True:
            code = self.scan_barcode()
            self.say("Code erkannt.")
            db = self.load_product_database()

            product_name = None
            for key, values in db.items():
                if code in values:
                    product_name = key

            if product_name:
                self.say(f"Ich schreibe {product_name} auf deine Einkaufsliste.")
                self.add_item_to_einkaufsliste(product_name)
            else:
                codes_todo.append(code)
                self.say("Unbekanntes Produkt. Bitte in der Datenbank ergänzen!")


class WebInterface:
    def __init__(self):
        self.app = Flask(__name__)
        self.setup_routes()

    def add_to_database(self, code, name):
        name = name.strip()
        code = code.strip()
        with open("product_database.txt", "r", encoding="utf8") as file:
            lines = file.readlines()

            found = False
            for index, line in enumerate(lines):
                line = line[:-1]
                if line.split(":")[0] == name:
                    found = True
                    if code not in line.split(": ")[1].split(", "):
                        line += f", {code}\n"
                        lines[index] = line
                    break

            if not found:
                lines.append(f"{name}: {code}\n")

        with open("product_database.txt", "w", encoding="utf8") as file:
            file.write("".join(sorted(lines)))

    def generate_entries(self):
        with open("product_database.txt", "r", encoding="utf8") as file:
            return "\n".join([f"<div class='item'>{entry.split(':')[0]}</div>" for entry in file.readlines()])

    def setup_routes(self):
        @self.app.route('/')
        def home():
            time.sleep(0.1)
            code = next(iter(codes_todo), None)
            if not code:
                code = "Aktuell keine zu indizierenden Produkte"
            return render_template("index.html", entries=self.generate_entries(), code=code)

        @self.app.route('/new', methods=["POST"])
        def new():
            if request.json["item_code"] in codes_todo:
                codes_todo.remove(request.json["item_code"])

            if request.json["item_selected"] == "+ NEUER EINTRAG":
                self.add_to_database(request.json["item_code"], request.json["item_name"])
            else:
                self.add_to_database(request.json["item_code"], request.json["item_selected"])
            return Response("{}", status=200, mimetype='application/json')

        @self.app.route('/discard', methods=["POST"])
        def discard():
            if request.json["item_code"] in codes_todo:
                codes_todo.remove(request.json["item_code"])
            return Response("{}", status=200, mimetype='application/json')

    def run(self, host="0.0.0.0", port=80):
        self.app.run(host=host, port=port, debug=True, use_reloader=False)


if __name__ == "__main__":
    interface = WebInterface()
    interface_thread = threading.Thread(target=interface.run)
    interface_thread.start()

    manager = StockManager()
    manager.start()

    interface_thread.join()
