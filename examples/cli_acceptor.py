import asyncio
import logging
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine

# Basic logging setup for the example
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class DummyApplication:
    async def onMessage(self, message):
        logger.info(f"DummyApp ACCEPTOR Received message: {message.to_wire(pretty=True) if hasattr(message, 'to_wire') else message}")

    async def onDisconnect(self, reason): # Optional: if your engine calls this
        logger.info(f"DummyApp ACCEPTOR Disconnected: {reason}")


async def main():
    # Configure the FIX engine for acceptor mode
    # Ensure pyfixmsg_plus/config.ini is present and configured correctly
    # or provide a full path if it's elsewhere.
    config = ConfigManager("pyfixmsg_plus/config.ini") 
    config.set('FIX', 'mode', 'acceptor')
    config.set('FIX', 'sender', 'ACCEPTOR') # This should match TargetCompID of initiator
    config.set('FIX', 'target', 'INITIATOR') # This should match SenderCompID of initiator
    config.set('FIX', 'host', '127.0.0.1')
    config.set('FIX', 'port', '5000')
    config.set('FIX', 'use_tls', 'false')
    # Ensure heartbeat interval is set, e.g., in config.ini or here
    config.set('FIX', 'heartbeat_interval', '30')


    engine = FixEngine(config, DummyApplication())
    
    try:
        logger.info("Starting acceptor engine...")
        # engine.connect() in acceptor mode should start listening (e.g., by calling network.start_accepting)
        # This call will block as long as the server is running (due to serve_forever).
        await engine.connect() 
        # The following lines will only be reached if engine.connect() (and thus start_accepting) returns,
        # which usually means the server has been stopped.
        logger.info("Acceptor engine has stopped listening.")
    except KeyboardInterrupt:
        logger.info("Acceptor shutting down due to KeyboardInterrupt...")
    except Exception as e:
        logger.error(f"Error in acceptor: {e}", exc_info=True)
    finally:
        if hasattr(engine, 'disconnect') and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring acceptor engine is disconnected...")
            await engine.disconnect(graceful=True)
        logger.info("Acceptor main function finished.")

if __name__ == "__main__":
    asyncio.run(main())
