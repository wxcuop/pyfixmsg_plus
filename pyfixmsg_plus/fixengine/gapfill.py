from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

def send_gapfill(send_message, config_manager, seq_num, new_seq_num):
    message = FixMessage()
    message.update({
        8: config_manager.get('FIX', 'version', 'FIX.4.4'),
        35: '4',  # Sequence Reset (Gap Fill)
        49: config_manager.get('FIX', 'sender', 'SERVER'),
        56: self.config_manager.get('FIX', 'target', 'CLIENT'),
        34: seq_num,
        36: new_seq_num,  # New sequence number
        123: 'Y',  # Gap Fill Flag
        52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
    })
    send_message(message)
