import os
import json
import time
import socket
import ssl
import logging
import configparser
from pyfixmsg.fixmessage import FixMessage

logging.basicConfig(level=logging.INFO)

class FixSession:
    def __init__(self, config_path='config.ini'):
        """
        Initializes the FIX session by reading settings from config.ini.
        
        :param config_path: Path to your configuration file (default: 'config.ini')
        """
        # Load configuration from file
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        
        # Read necessary settings from the [FIX] section
        self.sender_comp_id = self.config['FIX'].get('sender_comp_id', 'SENDER')
        self.target_comp_id = self.config['FIX'].get('target_comp_id', 'TARGET')
        self.host = self.config['FIX'].get('host', 'localhost')
        self.port = int(self.config['FIX'].get('port', '5000'))
        self.use_tls = self.config['FIX'].getboolean('use_tls', False)
        # Read the state_file path from config
        # Default file name: 'fix_session_state.json'
        self.state_file = self.config['FIX'].get('state_file', 'fix_session_state.json')

        self.sequence_number = 1
        self.is_logged_on = False
        self.connection = None
        self.message_store = {}  # Stores messages for potential resend requests

        # Load persisted sequence number state and message store if available
        self.load_state()

    def logon(self):
        """
        Sends a FIX Logon message to the counterparty.
        """
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
        """
        Sends a FIX Logout message to the counterparty.
        """
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
        """
        Sends a FIX Heartbeat message. Useful to keep the connection alive.
        """
        heartbeat_msg = FixMessage()
        heartbeat_msg.set_field(35, '0')  # MsgType = Heartbeat
        heartbeat_msg.set_field(49, self.sender_comp_id)
        heartbeat_msg.set_field(56, self.target_comp_id)
        heartbeat_msg.set_field(34, self.sequence_number)
        heartbeat_msg.set_field(52, time.strftime('%Y%m%d-%H:%M:%S'))
        self.send_message(heartbeat_msg)
        logging.info("Heartbeat sent")

    def send_message(self, message):
        """
        Serializes and sends a FIX message over the active connection.
        Also stores the message in message_store for possible resend.
        """
        if self.connection:
            encoded_msg = message.encode()
            self.connection.sendall(encoded_msg)
            # Store the message to handle resend requests
            self.message_store[self.sequence_number] = encoded_msg
            self.increment_sequence()

    def handle_resend_request(self, begin_seq_no, end_seq_no):
        """
        Handles a resend request by resending all messages in the specified range.
        If a message is missing, a gap fill message is sent.
        """
        for seq_no in range(begin_seq_no, end_seq_no + 1):
            if seq_no in self.message_store:
                self.connection.sendall(self.message_store[seq_no])
            else:
                # If a message isn't found, send a gap fill to indicate it was skipped
                self.send_gap_fill(seq_no, end_seq_no)
                break

    def send_gap_fill(self, begin_seq_no, end_seq_no):
        """
        Sends a Sequence Reset (Gap Fill) message indicating that certain messages
        have been skipped in response to a resend request.
        """
        gap_fill_msg = FixMessage()
        gap_fill_msg.set_field(35, '4')  # MsgType = Sequence Reset (Gap Fill)
        gap_fill_msg.set_field(49, self.sender_comp_id)
        gap_fill_msg.set_field(56, self.target_comp_id)
        gap_fill_msg.set_field(34, self.sequence_number)
        gap_fill_msg.set_field(123, 'Y')  # Gap Fill Flag
        gap_fill_msg.set_field(36, end_seq_no + 1)  # New Sequence Number
        self.send_message(gap_fill_msg)
        logging.info(f"Sent gap fill from {begin_seq_no} to {end_seq_no}")

    def increment_sequence(self):
        """
        Increments the outgoing sequence number and saves updated state.
        """
        self.sequence_number += 1
        self.save_state()

    def reset_sequence(self, new_sequence_number=1):
        """
        Resets the outgoing sequence number to a given value.
        This is often done after a successful logon or certain error conditions.
        """
        self.sequence_number = new_sequence_number
        self.save_state()
        logging.info(f"Sequence number reset to {self.sequence_number}")

    def connect(self):
        """
        Establishes a connection to the counterparty, either using TLS or plain TCP.
        """
        if self.use_tls:
            context = ssl.create_default_context()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection = context.wrap_socket(sock, server_hostname=self.host)
            logging.info("Using TLS for secure connection.")
        else:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.connection.connect((self.host, self.port))
        logging.info(f"Connected to {self.host}:{self.port}")

    def disconnect(self):
        """
        Closes the active connection.
        """
        if self.connection:
            self.connection.close()
            self.connection = None
            logging.info("Connection closed")

    def save_state(self):
        """
        Saves the current state (sequence number and message store) to a JSON file.
        """
        state = {
            'sequence_number': self.sequence_number,
            'message_store': self.message_store
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f)
        logging.info(f"State saved to {self.state_file}")

    def load_state(self):
        """
        Loads the persisted state (sequence number and message store) from a JSON file,
        if it exists. If not, defaults are used.
        """
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.sequence_number = state.get('sequence_number', 1)
                self.message_store = state.get('message_store', {})
            logging.info(f"State loaded from {self.state_file}")
        else:
            logging.info("No existing state file found. Starting fresh.")

class FixInitiator(FixSession):
    def start(self):
        """
        Starts the FIX Initiator by connecting, logging on, and sending heartbeats
        until the session is logged off or an exception occurs.
        """
        try:
            self.connect()
            self.logon()

            while self.is_logged_on:
                # Send periodic heartbeats
                self.send_heartbeat()
                time.sleep(30)  # Heartbeat interval (adjust as needed)

        except Exception as e:
            logging.error(f"Error in FixInitiator: {e}")
        finally:
            self.logout()
            self.disconnect()

class FixAcceptor(FixSession):
    def start(self):
        """
        Starts the FIX Acceptor by listening for incoming connections,
        accepting a connection, and sending heartbeats until the session
        is logged off or an exception occurs.
        """
        try:
            self.listen()
            self.accept_connection()

            while self.is_logged_on:
                # Send periodic heartbeats
                self.send_heartbeat()
                time.sleep(30)  # Heartbeat interval (adjust as needed)

        except Exception as e:
            logging.error(f"Error in FixAcceptor: {e}")
        finally:
            self.logout()
            self.disconnect()

    def listen(self):
        """
        Sets up a server socket to listen on the configured host and port.
        Uses TLS if configured, otherwise plain TCP.
        """
        if self.use_tls:
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logging.info(f"Listening with TLS on {self.host}:{self.port}")
        else:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logging.info(f"Listening on {self.host}:{self.port}")

    def accept_connection(self):
        """
        Accepts an incoming connection from a FIX Initiator.
        """
        client_socket, addr = self.server_socket.accept()
        self.connection = client_socket
        logging.info(f"Accepted connection from {addr}")
