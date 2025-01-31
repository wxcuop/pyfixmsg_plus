from datetime import datetime
from fixmessage_factory import FixMessageFactory

def send_gapfill(send_message, config_manager, new_seq_num):
    message = FixMessageFactory.create_message(
        '4',
        version=config_manager.get('FIX', 'version', 'FIX.4.4'),
        sender=config_manager.get('FIX', 'sender', 'SERVER'),
        target=config_manager.get('FIX', 'target', 'CLIENT'),
        new_seq_num=new_seq_num,
        gap_fill_flag='Y'
    )
    FixMessageFactory.return_message(message)
    send_message(message)
