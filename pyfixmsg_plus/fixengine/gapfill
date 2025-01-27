from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

def send_gapfill(send_message, target_comp_id, seq_num, new_seq_num):
    message = FixMessage()
    message.update({
        8: 'FIX.4.4',
        35: '4',  # Sequence Reset (Gap Fill)
        49: 'SERVER',
        56: target_comp_id,
        34: seq_num,
        36: new_seq_num,  # New sequence number
        123: 'Y',  # Gap Fill Flag
        52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
    })
    send_message(message)
