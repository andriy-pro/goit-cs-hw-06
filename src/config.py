import os

# Server settings from environment variables or default values
HTTP_HOST = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", 3000))
SOCKET_HOST = os.environ.get("SOCKET_HOST", "0.0.0.0")
SOCKET_PORT = int(os.environ.get("SOCKET_PORT", 5000))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/")
DB_NAME = os.environ.get("DB_NAME", "messages_db")
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "messages")
