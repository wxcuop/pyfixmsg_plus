import socket
import threading
import logging

class FIXEException(Exception):
    pass

class ListenSocket(threading.Thread):
    def __init__(self, listen_port, fe, logger):
        super().__init__()
        self.listen_port = listen_port
        self.fe = fe
        self.logger = logger
        self.s_socket = None
        self.c_socket = None
        self.is_stopping = False

    def start_listening(self):
        self.is_stopping = False
        self.logger.info("Listen Socket Start requested")
        try:
            self.s_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s_socket.bind(('', self.listen_port))
            self.s_socket.listen(1)
        except socket.error as e:
            raise FIXEException(f"Cannot create the listening socket: {e}")
        self.start()

    def stop_listening(self):
        self.is_stopping = True
        self.logger.info("Listen Socket Stop requested")
        if self.c_socket:
            try:
                self.c_socket.close()
            except socket.error as e:
                raise FIXEException(f"Could not close opened socket: {e}")
        if self.s_socket:
            try:
                self.s_socket.close()
            except socket.error as e:
                raise FIXEException(f"Could not close listen socket: {e}")

    def run(self):
        try:
            self.c_socket, addr = self.s_socket.accept()
        except socket.error as e:
            if not self.is_stopping:
                self.logger.error(f"Listen Socket while accepting connection: {e}")
        if not self.is_stopping:
            self.fe.set_socket(self.c_socket)
