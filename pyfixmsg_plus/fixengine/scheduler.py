import asyncio
import json
from datetime import datetime, timedelta
from configmanager import ConfigManager

class Scheduler:
    def __init__(self, config_file=None):
        self.config_manager = ConfigManager(config_file) if config_file else ConfigManager()
        self.schedules = []
        self.connection_settings = {}
        self.load_configuration()
        self.scheduler_task = asyncio.create_task(self.run_scheduler())

    def load_configuration(self):
        # Load the schedules and connection settings from the config manager
        schedule_json = self.config_manager.get('Scheduler', 'schedules', fallback='[]')
        self.schedules = json.loads(schedule_json)
        self.connection_settings = {
            "host": self.config_manager.get('FIX', 'host', '127.0.0.1'),
            "port": int(self.config_manager.get('FIX', 'port', '5000')),
            "sender": self.config_manager.get('FIX', 'sender', 'SENDER'),
            "target": self.config_manager.get('FIX', 'target', 'TARGET')
        }

    async def logon(self):
        # Implement the logon action
        print("Logon action executed")

    async def logout(self):
        # Implement the logout action
        print("Logout action executed")

    async def reset(self):
        # Implement the reset action
        print("Reset action executed")

    async def reset_logon(self):
        # Implement the reset and logon action
        await self.reset()
        await self.logon()

    async def logout_reset(self):
        # Implement the logout and reset action
        await self.logout()
        await self.reset()

    async def run_scheduler(self):
        while True:
            now = datetime.now().time()
            for task in self.schedules:
                task_time = datetime.strptime(task["time"], "%H:%M").time()
                if now >= task_time and (now - task_time) < timedelta(minutes=1):
                    action = getattr(self, task["action"], None)
                    if action:
                        await action()
            await asyncio.sleep(60)
