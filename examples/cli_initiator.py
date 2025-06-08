import asyncio
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine

class DummyApplication:
    async def onMessage(self, message):
        print(f"Received message: {message}")

async def main():
    # Configure the FIX engine for initiator mode
    config = ConfigManager("pyfixmsg_plus/config.ini")
    config.set('FIX', 'mode', 'initiator')
    config.set('FIX', 'sender', 'INITIATOR')
    config.set('FIX', 'target', 'ACCEPTOR')
    config.set('FIX', 'host', '127.0.0.1')  # Set host directly
    config.set('FIX', 'port', '5000')       # Set port directly
    config.set('FIX', 'use_tls', 'false')  # Disable TLS for debugging

    engine = FixEngine(config, DummyApplication())
    print("Connecting as initiator to 127.0.0.1:5000...")
    try:
        await engine.connect()
        print("Connected successfully!")
        await engine.logon()
        print("Logon process completed!")
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error encountered: {e}")

if __name__ == "__main__":
    asyncio.run(main())
