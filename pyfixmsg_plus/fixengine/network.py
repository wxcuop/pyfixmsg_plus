import socket
import threading
import logging

class Network:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.lock = threading.Lock()
        self.logger = logging.getLogger('Network')
        self.logger.setLevel(logging.DEBUG)

    def connect(self):
        with self.lock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            self.logger.info(f"Connected to {self.host}:{self.port}")

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
    def __init__(self, host, port):
        super().__init__(host, port)

    def accept(self):
        with self.lock:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.client_socket, self.client_address = self.socket.accept()
            self.logger.info(f"Accepted connection from {self.client_address}")

    def disconnect(self):
        with self.lock:
            self.client_socket.close()
            super().disconnect()

class Initiator(Network):
    def __init__(self, host, port):
        super().__init__(host, port)
