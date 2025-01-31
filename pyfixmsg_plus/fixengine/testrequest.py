from datetime import datetime
from fixmessage_factory import FixMessageFactory

def send_test_request(send_message, config_manager, seq_num):
    message = FixMessageFactory.create_message(
        '1',
        version=config_manager.get('FIX', 'version', 'FIX.4.4'),
        sender=config_manager.get('FIX', 'sender', 'SERVER'),
        target=config_manager.get('FIX', 'target', 'CLIENT'),
        seq_num=seq_num,
        test_req_id='TestReqID'
    )
    FixMessageFactory.return_message(message)
    send_message(message)
