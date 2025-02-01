import asyncio
import logging
from fixmessage_factory import FixMessageFactory

class ResendHandler:
    def __init__(self, message_store, version, sender, target):
        self.message_store = message_store
        self.version = version
        self.sender = sender
        self.target = target
        self.logger = logging.getLogger('ResendHandler')

    async def send_resend_request(self, begin_seq_no, end_seq_no, send_message_callback):
        resend_request_message = FixMessageFactory.create_message('2')
        resend_request_message[49] = self.sender
        resend_request_message[56] = self.target
        resend_request_message[7] = begin_seq_no
        resend_request_message[16] = end_seq_no
        await send_message_callback(resend_request_message)
        self.logger.info(f"Sent Resend Request: BeginSeqNo={begin_seq_no}, EndSeqNo={end_seq_no}")

    async def handle_resend_request(self, message, send_message_callback):
        start_seq_num = int(message.get('7'))  # Get the start sequence number from the resend request
        end_seq_num = int(message.get('16'))  # Get the end sequence number from the resend request
        self.logger.info(f"Received Resend Request: BeginSeqNo={start_seq_num}, EndSeqNo={end_seq_num}")
        
        if end_seq_num == 0:
            end_seq_num = self.message_store.get_next_outgoing_sequence_number() - 1
        
        for seq_num in range(start_seq_num, end_seq_num + 1):
            stored_message = self.message_store.get_message(self.version, self.sender, self.target, seq_num)
            if stored_message:
                await send_message_callback(stored_message)
            else:
                await self.send_gap_fill_message(seq_num, send_message_callback)

    async def send_gap_fill_message(self, seq_num, send_message_callback):
        gap_fill_message = FixMessageFactory.create_message('4')  # Sequence Reset
        gap_fill_message[123] = 'Y'  # Gap Fill Flag
        gap_fill_message[36] = seq_num
        await send_message_callback(gap_fill_message)
        self.logger.info(f"Sent Gap Fill message for sequence number: {seq_num}")
