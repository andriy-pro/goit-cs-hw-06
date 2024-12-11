import logging
import mimetypes
import socket
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from socketserver import ThreadingMixIn
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from urllib.parse import urlparse, parse_qs
import json
import os
import config  # Import configuration from config.py

# Use imported config variables
HTTP_HOST = config.HTTP_HOST
HTTP_PORT = config.HTTP_PORT
SOCKET_HOST = config.SOCKET_HOST
SOCKET_PORT = config.SOCKET_PORT
MONGO_URI = config.MONGO_URI
DB_NAME = config.DB_NAME
COLLECTION_NAME = config.COLLECTION_NAME

# Логування
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# HTTP Handler
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    """HTTP-обробник запитів з методами GET та POST."""
    
    def do_GET(self):
        """Обробляє GET-запити від клієнта."""
        parsed_path = urlparse(self.path)
        route = parsed_path.path
        match route:
            case '/' | '/index.html':
                self.send_html_file("index.html")
            case '/message.html':
                self.send_html_file("message.html")
            case '/error.html':
                self.send_html_file("error.html")
            case _ if route.startswith("/static/"):
                self.send_static_file(route[1:])
            case _:
                self.send_error_page()

    def do_POST(self):
        """Обробляє POST-запити від клієнта."""
        if self.path == "/message":
            content_length = int(self.headers.get("Content-Length"))
            body = self.rfile.read(content_length)
            params = parse_qs(body.decode())
            message = {
                "username": params.get("username", [""])[0],
                "message": params.get("message", [""])[0],
            }
            self.send_to_socket(message)
            self.redirect_to_home()
        else:
            self.send_error_page()

    def send_to_socket(self, message):
        """Відправляє повідомлення до сокет-сервера."""
        # Валідація вхідних даних
        if not message.get("username") or not message.get("message"):
            logging.error("Відсутні обов'язкові поля 'username' або 'message'")
            self.send_error_page()
            return
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                client_socket.connect((SOCKET_HOST, SOCKET_PORT))
                client_socket.sendall(json.dumps(message).encode("utf-8"))
        except Exception as e:
            logging.error(f"Помилка при відправці до сокет-сервера: {e}")

    def redirect_to_home(self):
        """Перенаправляє клієнта на головну сторінку."""
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html_file(self, filename, status_code=200):
        """Надсилає HTML-файл клієнту."""
        try:
            with open(filename, "rb") as file:
                self.send_response(status_code)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_error_page()

    def send_static_file(self, filepath):
        """Надсилає статичний файл клієнту."""
        try:
            mimetype, _ = mimetypes.guess_type(filepath)
            with open(filepath, "rb") as file:
                self.send_response(200)
                self.send_header("Content-type", mimetype or "application/octet-stream")
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_error_page()

    def send_error_page(self):
        """Надсилає сторінку помилки клієнту."""
        self.send_html_file("error.html", status_code=404)

# Threading HTTP Server
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Багатопотоковий HTTP-сервер для обробки запитів."""
    pass

# Socket Server
def run_socket_server():
    """Запускає сокет-сервер для отримання повідомлень та збереження їх у MongoDB."""
    try:
        # Перевірка підключення до MongoDB
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        logging.info("Підключення до MongoDB встановлено")
    except ConnectionFailure:
        logging.error("Не вдалося підключитися до MongoDB")
        return
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((SOCKET_HOST, SOCKET_PORT))
        server_socket.listen(5)
        logging.info(f"Сокет-сервер запущено на {SOCKET_HOST}:{SOCKET_PORT}")
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_socket_connection, args=(conn, addr, collection))
            thread.start()

# Handle socket connections
def handle_socket_connection(conn, addr, collection):
    """Обробляє з'єднання сокет-сервера з клієнтом."""
    try:
        data = conn.recv(1024)
        if data:
            message = json.loads(data.decode("utf-8"))
            message["date"] = datetime.now()  # Store datetime object
            try:
                collection.insert_one(message)
                logging.info(f"Збережено повідомлення: {message}")
            except Exception as e:
                logging.error(f"Error inserting message into MongoDB: {e}")
    except Exception as e:
        logging.error(f"Помилка обробки сокет-запиту від {addr}: {e}")
    finally:
        conn.close()

# HTTP Server Runner
def run_http_server():
    """Запускає HTTP-сервер."""
    server = ThreadedHTTPServer((HTTP_HOST, HTTP_PORT), SimpleHTTPRequestHandler)
    logging.info(f"HTTP-сервер запущено на {HTTP_HOST}:{HTTP_PORT}")
    server.serve_forever()

if __name__ == "__main__":
    """Стартує HTTP та сокет-сервери у окремих процесах."""
    http_process = Process(target=run_http_server)
    socket_process = Process(target=run_socket_server)

    http_process.start()
    socket_process.start()

    http_process.join()
    socket_process.join()