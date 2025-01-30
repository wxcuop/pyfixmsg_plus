from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

def send_test_request(send_message, config_manager, seq_num):
    message = FixMessage()
    message.update({
        8: config_manager.get('FIX', 'version', 'FIX.4.4'),
        35: '1',  # Test Request
        49: config_manager.get('FIX', 'sender', 'SERVER'),
        56: config_manager.get('FIX', 'target', 'CLIENT'), 
        34: seq_num,
        52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3],
        112: 'TestReqID'  # Test Request ID
    })
    send_message(message)
