from fixnetwork import SocketConnector, ListenSocket

class ConnectionManager:
    def __init__(self, event_notifier):
        self.event_notifier = event_notifier
        self.m_socket_connector = SocketConnector(event_notifier)
        self.listen_socket = None

    def open_connection(self, host, service):
        self.m_socket_connector.open_connection(host, service)

    def set_socket(self, socket):
        self.m_socket_connector.set_socket(socket)

    def close_connection(self):
        self.m_socket_connector.close_connection()

    def begin_listen_socket(self, service, logger):
        self.listen_socket = ListenSocket(service, self, logger)
        self.listen_socket.start()  # throws FIXEException if fails

    def stop_listen_incoming_connections(self, logger):
        if self.listen_socket is not None:
            try:
                self.listen_socket.stop()
            except FIXEException as e:
                logger.warn(f"Exception while stopping the listen socket {str(e)}")
