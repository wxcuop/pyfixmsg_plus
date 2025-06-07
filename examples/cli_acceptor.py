import asyncio
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine

class DummyApplication:
    async def onMessage(self, message):
        print(f"Received message: {message}")

async def main():
    # Load config (adjust the path as needed)
    config = ConfigManager("pyfixmsg_plus/config.ini")
    config.set('FIX', 'mode', 'acceptor')
    config.set('FIX', 'sender', 'ACCEPTOR')
    config.set('FIX', 'target', 'INITIATOR')
    config.set('FIX', 'host', '127.0.0.1')
    config.set('FIX', 'port', '5000')
    config.set('FIX', 'use_tls', 'false')  # Temporarily disable TLS for debugging

    engine = FixEngine(config, DummyApplication())
    print("Starting acceptor...")
    await engine.network.start_accepting(engine.handle_incoming_connection)
    print("Acceptor is running on 127.0.0.1:5000")
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
