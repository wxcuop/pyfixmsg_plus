import socket
import logging

class FIXEException(Exception):
    pass

class SocketConnector:
    def __init__(self, event_notifier):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.event_notifier = event_notifier
        self.socket_initiator = None
        self.o_stream_s = None
        self.i_stream_s = None
        self.in_closing_process = False

    def open_connection(self, host, port):
        if self.is_connection_open():
            self.logger.warn("Connection is already open")
            self.event_notifier.notify_msg("SocketConnector.open_connection() Connection is already open", "WARNING")
            return False

        self.close_connection()
        self.in_closing_process = False

        try:
            self.socket_initiator = socket.create_connection((host, port))
        except socket.gaierror as e:
            self.logger.error(f"UnknownHostException, could not connect to server {host}:{port}, {e}")
            raise FIXEException(f"SocketConnector.open_connection() UnknownHostException, could not connect to server {host}:{port}, {e}")
        except socket.error as e:
            self.logger.error(f"IOException, could not connect to server {host}:{port}, {e}")
            raise FIXEException(f"SocketConnector.open_connection() IOException, could not connect to server {host}:{port}, {e}")

        if not self.open_io_streams():
            self.close_connection()
            return False

        self.logger.info(f"Successfully Opened Connection to {host}:{port}")
        return True

    def set_socket(self, existing_socket):
        if existing_socket == self.socket_initiator:
            self.logger.warn("Socket already set")
            return True

        if self.is_connection_open():
            self.event_notifier.notify_msg("SocketConnector.set_socket() Connection is already open", "WARNING")
            self.logger.warn("Connection is already open")
            return False

        self.close_connection()
        self.in_closing_process = False
        self.socket_initiator = existing_socket

        if not self.open_io_streams():
            return False

        self.logger.info("Successfully Set New Socket")
        return True

    def open_io_streams(self):
        try:
            self.o_stream_s = self.socket_initiator.makefile('wb')
        except IOError as e:
            self.logger.error(f"IOException, can get output stream {e}")
            self.event_notifier.notify_msg(f"m_socketInitiator.write_to_socket() raised IOException, {e}", "ERROR")
            return False

        try:
            self.i_stream_s = self.socket_initiator.makefile('rb')
        except IOError as e:
            self.logger.error(f"IOException, cannot get input stream {e}")
            self.event_notifier.notify_msg(f"m_socketInitiator.get_input_stream() raised IOException, {e}", "ERROR")
            return False

        return True

    def is_connection_open(self):
        if not self.socket_initiator:
            return False

        if not self.socket_initiator.fileno():
            return False

        return True

    def close_connection(self):
        self.in_closing_process = True

        if self.i_stream_s:
            try:
                self.i_stream_s.close()
            except IOError as e:
                self.logger.error(f"IOException, closing input stream {e}")
                self.event_notifier.notify_msg(f"IOException while stop_listen_FIX_messages, {e}", "WARNING")
            self.i_stream_s = None

        if self.o_stream_s:
            try:
                self.o_stream_s.close()
            except IOError as e:
                self.logger.error(f"IOException, closing output stream {e}")
                self.event_notifier.notify_msg(f"Stop send raised IOException, {e}", "INFO")
            self.o_stream_s = None

        if self.socket_initiator:
            try:
                self.socket_initiator.close()
            except IOError as e:
                self.logger.error(f"IOException, closing socket {e}")
                self.event_notifier.notify_msg(f"Socket Server close error {e}", "WARNING")
            self.socket_initiator = None

    def read_from_socket(self, buffer, offset, length):
        if not self.is_connection_open():
            return -1

        if not self.i_stream_s:
            self.logger.error("i_stream_s == null")
            self.event_notifier.notify_msg("socket_initiator.read_from_socket i_stream_s == null", "INFO")
            return -1

        try:
            num_bytes = self.i_stream_s.readinto(buffer[offset:offset + length])
            return num_bytes
        except IOError as e:
            if not self.in_closing_process:
                self.logger.error(f"IOException reading input stream {e}")
            self.event_notifier.notify_msg(f"socket_initiator.read_from_socket raised IOException, {e}", "ERROR" if not self.in_closing_process else "INFO")
            return -1

    def read_char_from_socket(self):
        buffer = bytearray(1)
        if self.read_from_socket(buffer, 0, 1) != 1:
            return -1
        return buffer[0]

    def write_to_socket(self, message):
        if not self.is_connection_open():
            return False

        if not self.o_stream_s:
            self.logger.error("o_stream_s == null")
            self.event_notifier.notify_msg("socket_initiator.write_to_socket o_stream_s == null", "INFO")
            return False

        try:
            self.o_stream_s.write(message)
            self.o_stream_s.flush()
        except IOError as e:
            self.logger.error(f"IOException writing output stream {e}")
            self.event_notifier.notify_msg(f"SocketConnector.OutputStream.write raised IOException, {e}", "ERROR")
            raise FIXEException(f"SocketConnector.OutputStream.write raised IOException, {e}")

        return True
