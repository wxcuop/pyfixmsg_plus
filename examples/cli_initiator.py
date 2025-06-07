import asyncio
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine

class DummyApplication:
    async def onMessage(self, message):
        print(f"Received message: {message}")

async def main():
    # Load config (adjust the path as needed)
    config = ConfigManager("pyfixmsg_plus/config.ini")
    # Ensure mode is 'initiator'
    config.set('FIX', 'mode', 'initiator')
    # Set SENDER and TARGET as needed
    config.set('FIX', 'sender', 'INITIATOR')
    config.set('FIX', 'target', 'ACCEPTOR')
    
    # Set host and port directly
    config.set('FIX', 'host', '127.0.0.1')  # Directly set the host
    config.set('FIX', 'port', '5000')       # Directly set the port

    # Create and connect the engine
    engine = FixEngine(config, DummyApplication())
    await engine.connect()
    await engine.logon()
    # Keep running to demonstrate heartbeat
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
