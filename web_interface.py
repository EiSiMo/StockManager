import threading
import logging
import time
import os
import pygments
import pygments.lexers
import pygments.formatters
from flask import Flask, render_template, Response, request, send_from_directory

logger = logging.getLogger("Root")


class WebInterface(threading.Thread):
    def __init__(self, manager):
        super().__init__()

        self.manager = manager
        self.app = Flask(__name__)
        self.setup_routes()

        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        null_handler = logging.NullHandler()
        logging.getLogger().addHandler(null_handler)
        self.running = True

    def generate_entries(self):
        logger.debug(f"generate_entries() called")
        result = ""
        for name in self.manager.product_database.keys():
            result += f"<div class='item'>{name}</div>\n"
        return result

    def generate_logs(self):
        logger.debug(f"generate_logs() called")
        with open("logs/log.log", "r", encoding="utf8") as file:
            text = file.read()
        lexer = pygments.lexers.TextLexer()
        html_formatter = pygments.formatters.HtmlFormatter(style="colorful", full=True, linenos=True, encoding="utf8")

        highlighted_code = pygments.highlight(text, lexer, html_formatter)

        return highlighted_code

    def generate_rawdb(self):
        logger.debug(f"generate_rawdb() called")
        with open("product_database.txt", "r", encoding="utf8") as file:
            text = file.read()
        lexer = pygments.lexers.TextLexer()
        html_formatter = pygments.formatters.HtmlFormatter(style="colorful", full=True, linenos=True, encoding="utf8")

        highlighted_code = pygments.highlight(text, lexer, html_formatter)

        return highlighted_code

    def setup_routes(self):
        logger.info(f"setup_routes() called")

        @self.app.before_request
        def log_request_info():
            logger.info(f"request: {request.method} {request.path} ({request.remote_addr})")

        @self.app.route("/")
        def home():
            logger.debug(f"waiting 0.1s to make sure the database has finished saving changes")
            time.sleep(0.1)
            if self.manager.codes_todo.empty():
                code = "Aktuell keine zu indizierenden Produkte"
            else:
                code = self.manager.codes_todo.get()
            logger.debug(f"fetched '{code}' from todo list")
            logger.info(f"sending response 200 OK")
            return render_template("index.html", entries=self.generate_entries(), code=code)

        @self.app.route("/new", methods=["POST"])
        def new():
            name = request.json["name"]
            code = request.json["code"]

            logger.info(f"adding {name} and {code} to the database")
            self.manager.product_database[name] = code

            logger.info(f"sending response 200 OK")
            return Response("{}", status=200, mimetype="application/json")

        @self.app.route("/logs")
        def logs():
            return self.generate_logs()

        @self.app.route("/rawdb")
        def rawdb():
            return self.generate_rawdb()

        @self.app.route("/favicon.ico")
        def favicon():
            return send_from_directory(os.path.join(self.app.root_path, "static/images"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.error("Unhandled exception", exc_info=(type(e), e, e.__traceback__))
            return "Internal Server Error", 500

    def run(self):
        try:
            self.app.run(host="0.0.0.0", port=80, debug=True, use_reloader=False)
        except Exception as e:
            logger.error("Exception in WebInterface thread", exc_info=e)
            self.running = False
