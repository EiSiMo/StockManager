import re
import logging
import queue
import threading
from todoist_api_python.api import TodoistAPI
from product_database import ProductDatabase

logger = logging.getLogger("Root")


class StockManager(threading.Thread):
    def __init__(self, barcode_queue, saying_queue):
        super().__init__()
        self.barcode_queue = barcode_queue
        self.saying_queue = saying_queue

        self.todoist_api_key = open("api_key.txt", "r", encoding="utf8").read()
        self.todoist_project_id = "2336429901"
        self.product_database = ProductDatabase("product_database.txt")
        self.codes_todo = queue.Queue()
        self.running = True

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

    def process_barcode(self, code):
        logger.info(f"barcode '{code}' detected")
        logger.info(f"testing barcode validity")
        valid_barcode_regex = re.compile(r"^\d*$")
        if re.fullmatch(valid_barcode_regex, code):
            logger.debug(f"barcode valid - searching barcode in database")
            product_name = self.product_database.find(code)

            if product_name:
                logger.info(f"barcode already in database")
                self.saying_queue.put(f"Ich schreibe {product_name} auf deine Einkaufsliste.")
                logger.info(f"adding item to shopping list")
                self.add_item_to_todoist(product_name)
            else:
                logger.info(f"barcode not in database yet")
                if code not in list(self.codes_todo.queue):
                    logger.debug(f"adding item to todo list")
                    self.codes_todo.put(code)
                    self.saying_queue.put("Unbekanntes Produkt - bitte in der Datenbank ergänzen!")
                else:
                    logger.debug(f"item already on todo list")
                    self.saying_queue.put("Bitte öffne die Webseite, um das Produkt einzutragen.")
        else:
            logger.info("barcode invalid")
            self.saying_queue.put("Fehler: Dieser Barcode ist nicht gültig.")

    def run(self):
        self.saying_queue.put("Vorratsmanager gestartet.")
        while self.running:
            try:
                code = self.barcode_queue.get(timeout=1)
                self.process_barcode(code)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error("Exception in StockManager thread", exc_info=e)
                self.running = False

