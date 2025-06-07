import asyncio
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine

class DummyApplication:
    async def onMessage(self, message):
        print(f"Received message: {message}")

async def main():
    # Load config (adjust the path as needed)
    config = ConfigManager("pyfixmsg_plus/config.ini")
    # Ensure mode is 'acceptor'
    config.set('FIX', 'mode', 'acceptor')
    # Set SENDER and TARGET as needed
    config.set('FIX', 'sender', 'ACCEPTOR')
    config.set('FIX', 'target', 'INITIATOR')
    # Create and start the engine (wait for initiator to connect)
    engine = FixEngine(config, DummyApplication())
    await engine.network.start_accepting(engine.handle_incoming_connection)  # Updated to start_accepting
    # Keep running to demonstrate heartbeat
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
