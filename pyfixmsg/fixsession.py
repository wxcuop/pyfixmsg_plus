import time
import socket
import ssl
from pyfixmsg.fixmessage import FixMessage
import logging

logging.basicConfig(level=logging.INFO)

class FixSession:
    def __init__(self, sender_comp_id, target_comp_id):
        self.sender_comp_id = sender_comp_id
        self.target_comp_id = target_comp_id
        self.sequence_number = 1
        self.is_logged_on = False
        self.connection = None

    def logon(self):
        logon_msg = FixMessage()
        logon_msg.set_field(35, 'A')  # MsgType = Logon
        logon_msg.set_field(49, self.sender_comp_id)
        logon_msg.set_field(56, self.target_comp_id)
        logon_msg.set_field(34, self.sequence_number)
        logon_msg.set_field(52, time.strftime('%Y%m%d-%H:%M:%S'))
        self.send_message(logon_msg)
        self.is_logged_on = True
        logging.info("Logged on to FIX session")

    def logout(self):
        logout_msg = FixMessage()
        logout_msg.set_field(35, '5')  # MsgType = Logout
        logout_msg.set_field(49, self.sender_comp_id)
        logout_msg.set_field(56, self.target_comp_id)
        logout_msg.set_field(34, self.sequence_number)
        logout_msg.set_field(52, time.strftime('%Y%m%d-%H:%M:%S'))
        self.send_message(logout_msg)
        self.is_logged_on = False
        logging.info("Logged out of FIX session")

    def send_heartbeat(self):
        heartbeat_msg = FixMessage()
        heartbeat_msg.set_field(35, '0')  # MsgType = Heartbeat
        heartbeat_msg.set_field(49, self.sender_comp_id)
        heartbeat_msg.set_field(56, self.target_comp_id)
        heartbeat_msg.set_field(34, self.sequence_number)
        heartbeat_msg.set_field(52, time.strftime('%Y%m%d-%H:%M:%S'))
        self.send_message(heartbeat_msg)
        logging.info("Heartbeat sent")

    def send_message(self, message):
        if self.connection:
            encoded_msg = message.encode()
            self.connection.sendall(encoded_msg)
            self.increment_sequence()

    def increment_sequence(self):
        self.sequence_number += 1

    def reset_sequence(self):
        self.sequence_number = 1

    def connect(self, host, port, use_tls=False):
        if use_tls:
            context = ssl.create_default_context()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection = context.wrap_socket(sock, server_hostname=host)
        else:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connection.connect((host, port))
        logging.info(f"Connected to {host}:{port}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            logging.info("Connection closed")
            
# FixInitiator class in fixsession.py
class FixInitiator(FixSession):
    def start(self, host, port, use_tls=False):
        try:
            self.connect(host, port, use_tls)
            self.logon()

            while self.is_logged_on:
                # Handle messages and heartbeats
                self.send_heartbeat()
                time.sleep(30)  # Example heartbeat interval

        except Exception as e:
            logging.error(f"Error: {e}")
        finally:
            self.logout()
            self.disconnect()

# FixAcceptor class in fixsession.py
class FixAcceptor(FixSession):
    def start(self, host, port, use_tls=False):
        try:
            self.listen(host, port, use_tls)
            self.accept_connection()

            while self.is_logged_on:
                # Handle messages and heartbeats
                self.send_heartbeat()
                time.sleep(30)  # Example heartbeat interval

        except Exception as e:
            logging.error(f"Error: {e}")
        finally:
            self.logout()
            self.disconnect()

    def listen(self, host, port, use_tls=False):
        if use_tls:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            logging.info(f"Listening for connections on {host}:{port} with TLS")
        else:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((host, port))
            self.server_socket.listen(5)
            logging.info(f"Listening for connections on {host}:{port} without TLS")

    def accept_connection(self):
        client_socket, addr = self.server_socket.accept()
        self.connection = client_socket
        logging.info(f"Accepted connection from {addr}")
