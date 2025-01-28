import socket
import ssl
import threading
import logging

class Network:
    def __init__(self, host, port, use_tls=False):
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self.socket = None
        self.running = False
        self.lock = threading.Lock()
        self.logger = logging.getLogger('Network')
        self.logger.setLevel(logging.DEBUG)

    def connect(self):
        with self.lock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.use_tls:
                context = ssl.create_default_context()
                self.socket = context.wrap_socket(self.socket, server_hostname=self.host)
            self.socket.connect((self.host, self.port))
            self.running = True
            self.logger.info(f"Connected to {self.host}:{self.port} with TLS={self.use_tls}")

    def disconnect(self):
        with self.lock:
            self.running = False
            if self.socket:
                self.socket.close()
            self.logger.info("Disconnected")

    def send(self, message):
        with self.lock:
            self.socket.sendall(message)
            self.logger.info(f"Sent: {message}")

    def receive(self, handler):
        while self.running:
            data = self.socket.recv(4096)
            if data:
                handler(data)

class Acceptor(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)

    def accept(self):
        with self.lock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.client_socket, self.client_address = self.socket.accept()
            if self.use_tls:
                context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                self.client_socket = context.wrap_socket(self.client_socket, server_side=True)
            self.logger.info(f"Accepted connection from {self.client_address}")

    def disconnect(self):
        with self.lock:
            if self.client_socket:
                self.client_socket.close()
            super().disconnect()

class Initiator(Network):
    def __init__(self, host, port, use_tls=False):
        super().__init__(host, port, use_tls)
