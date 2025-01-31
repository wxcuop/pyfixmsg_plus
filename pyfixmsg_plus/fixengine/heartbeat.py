import asyncio
from datetime import datetime
from fixmessage_factory import FixMessageFactory

class Heartbeat:
    def __init__(self, send_message, config_manager, interval=30):
        self.send_message = send_message
        self.config_manager = config_manager
        self.interval = self.config_manager.get('FIX', 'interval', 30)
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
            message = FixMessageFactory.create_message(
                '0',
                version=self.config_manager.get('FIX', 'version', 'FIX.4.4'),
                sender=self.config_manager.get('FIX', 'sender', 'SERVER'),
                target=self.config_manager.get('FIX', 'target', 'CLIENT')
            )
            await self.send_message(message)
            FixMessageFactory.return_message(message)
            await asyncio.sleep(self.interval)
