from unittest.mock import patch, MagicMock

def test_fix_initiator_connect(fix_initiator):
    with patch('socket.socket.connect') as mock_connect:
        mock_connect.return_value = None
        fix_initiator.connect()
        assert fix_initiator.connection is not None
        mock_connect.assert_called_once_with(('localhost', 5000))

def test_fix_acceptor_listen(fix_acceptor):
    with patch('socket.socket.bind') as mock_bind, patch('socket.socket.listen') as mock_listen:
        mock_bind.return_value = None
        mock_listen.return_value = None
        fix_acceptor.listen()
        assert fix_acceptor.server_socket is not None
        mock_bind.assert_called_once_with(('localhost', 5000))
        mock_listen.assert_called_once_with(5)

def test_fix_acceptor_accept_connection(fix_acceptor):
    with patch('socket.socket.accept') as mock_accept:
        mock_client_socket = MagicMock()
        mock_accept.return_value = (mock_client_socket, ('localhost', 12345))
        fix_acceptor.listen()
        fix_acceptor.accept_connection()
        assert fix_acceptor.connection == mock_client_socket
        mock_accept.assert_called_once()
