import asyncio
import logging
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine

# Basic logging setup for the example
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class DummyApplication:
    async def onMessage(self, message):
        logger.info(f"DummyApp INITIATOR Received message: {message.to_wire(pretty=True) if hasattr(message, 'to_wire') else message}")

    async def onDisconnect(self, reason): # Optional: if your engine calls this
        logger.info(f"DummyApp INITIATOR Disconnected: {reason}")

async def main():
    # Configure the FIX engine for initiator mode
    # Ensure pyfixmsg_plus/config.ini is present and configured correctly
    # or provide a full path if it's elsewhere.
    config = ConfigManager("pyfixmsg_plus/config.ini")
    config.set('FIX', 'mode', 'initiator')
    config.set('FIX', 'sender', 'INITIATOR') # This should match TargetCompID of acceptor
    config.set('FIX', 'target', 'ACCEPTOR') # This should match SenderCompID of acceptor
    config.set('FIX', 'host', '127.0.0.1')
    config.set('FIX', 'port', '5000')
    config.set('FIX', 'use_tls', 'false')
    # Ensure heartbeat interval is set, e.g., in config.ini or here
    config.set('FIX', 'heartbeat_interval', '30')


    engine = FixEngine(config, DummyApplication())
    
    try:
        logger.info("Starting initiator engine and connecting to 127.0.0.1:5000...")
        # engine.connect() in initiator mode should:
        # 1. Establish TCP/IP connection.
        # 2. Send a Logon message.
        # 3. Start the message receiving loop.
        await engine.connect()
        
        # The Logon message is sent by engine.connect() itself in initiator mode.
        # No need for an explicit `await engine.logon()` here.
        logger.info("Initiator engine.connect() completed. Session establishment in progress.")
        
        # Keep the script running to allow the engine's async tasks (heartbeating, message receiving) to operate.
        # The actual session state (e.g., ACTIVE) is managed internally by the engine and its state machine.
        while engine.state_machine.state.name != 'DISCONNECTED': # Keep running as long as not disconnected
            if engine.state_machine.state.name == 'ACTIVE':
                # Optionally, send a test message once active
                # For example, after a short delay to ensure session is stable:
                # await asyncio.sleep(5)
                # test_msg = engine.fixmsg({35: 'D', 11: 'TestOrder1', 54: '1', 38: '100', 40: '1'})
                # logger.info("Sending a test NewOrderSingle")
                # await engine.send_message(test_msg)
                # await asyncio.sleep(30) # Wait a bit more
                # break # Or break after sending a test message
                pass # Just keep alive while active

            await asyncio.sleep(1)
        logger.info(f"Initiator loop finished. Engine state: {engine.state_machine.state.name}")

    except KeyboardInterrupt:
        logger.info("Initiator shutting down due to KeyboardInterrupt...")
    except Exception as e:
        logger.error(f"Error in initiator: {e}", exc_info=True)
    finally:
        if hasattr(engine, 'disconnect') and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring initiator engine is disconnected...")
            await engine.disconnect(graceful=True) # Attempt graceful logout
        logger.info("Initiator main function finished.")

if __name__ == "__main__":
    asyncio.run(main())
