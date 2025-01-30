import asyncio
from datetime import datetime
from pyfixmsg.fixmessage import FixMessage

class Heartbeat:
    def __init__(self, send_message, config_manager, interval=30):
        self.send_message = send_message
        self.config_manager = config_manager
        self.interval = self.config_manager.get('FIX', 'interval', 30),
        self.running = False
        self.task = None

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._send_heartbeat())

    async def stop(self):
        self.running = False
        if self.task:
            await self.task

    async def _send_heartbeat(self):
        while self.running:
            message = FixMessage()
            message.update({
                8: self.config_manager.get('FIX', 'version', 'FIX.4.4'),
                35: '0',  # Heartbeat
                49: self.config_manager.get('FIX', 'sender', 'SERVER'),
                56: self.config_manager.get('FIX', 'target', 'CLIENT'),
                34: 1,  # This should be dynamically set
                52: datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")[:-3]
            })
            await self.send_message(message)
            await asyncio.sleep(self.interval)
