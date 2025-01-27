from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

def send_test_request(send_message, target_comp_id, seq_num):
    message = FixMessage()
    message.update({
        8: 'FIX.4.4',
        35: '1',  # Test Request
        49: 'SERVER',
        56: target_comp_id,
        34: seq_num,
        52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3],
        112: 'TestReqID'  # Test Request ID
    })
    send_message(message)
