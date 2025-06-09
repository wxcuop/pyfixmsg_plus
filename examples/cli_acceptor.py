import asyncio
import logging
import os
from pyfixmsg_plus.fixengine.engine import FixEngine
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.application import Application # CORRECTED IMPORT

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class DummyApplication(Application):
    async def onLogon(self, message, session_id):
        logger.info(f"[{session_id}] Application: Logon successful. Message: {message.to_wire(pretty=True)}")

    async def onLogout(self, message, session_id):
        logger.info(f"[{session_id}] Application: Logout. Message: {message.to_wire(pretty=True)}")

    async def onMessage(self, message, session_id):
        logger.info(f"[{session_id}] Application: Received message type {message.get(35)}: {message.to_wire(pretty=True)}")
        # Example: if it's a NewOrderSingle, send an ExecutionReport
        if message.get(35) == 'D': # NewOrderSingle
            exec_report = self.engine.fixmsg({ # Assuming self.engine is set by FixEngine on app
                35: '8', # ExecutionReport
                11: message.get(11), # ClOrdID
                37: f"exec-{message.get(11)}", # OrderID
                17: f"execid-{message.get(11)}", # ExecID
                150: '0', # ExecType = New
                39: '0', # OrdStatus = New
                55: message.get(55), # Symbol
                54: message.get(54), # Side
                44: message.get(44) if 44 in message else 0, # Price
                38: message.get(38), # OrderQty
                14: 0, # CumQty
                6: 0, # AvgPx
                # Add other necessary fields
            })
            logger.info(f"[{session_id}] Application: Sending ExecutionReport for {message.get(11)}")
            await self.engine.send_message(exec_report)


    def set_engine(self, engine): # Add this method to your Application base or here
        self.engine = engine


async def main():
    logger.info("Starting acceptor engine...")
    # Determine the path to the config file relative to this script
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config_acceptor.ini')
    
    config = ConfigManager(config_path)
    app = DummyApplication()
    engine = FixEngine(config, app)
    app.set_engine(engine) # Allow app to access engine for sending messages

    try:
        # Use engine.start() instead of engine.connect()
        await engine.start()
    except KeyboardInterrupt:
        logger.info("Acceptor engine shutting down by user request (KeyboardInterrupt)...")
    except Exception as e:
        logger.error(f"Error in acceptor: {e}", exc_info=True)
    finally:
        if engine and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring engine is disconnected...")
            await engine.disconnect(graceful=True)
        logger.info("Acceptor main function finished.")

if __name__ == "__main__":
    # Clean up previous db if it exists for a fresh run
    db_path_config = ConfigManager(os.path.join(os.path.dirname(__file__), 'config_acceptor.ini'))
    db_file = db_path_config.get('FIX', 'state_file', 'acceptor_fix_state.db')
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
            logger.info(f"Removed previous state file: {db_file}")
        except OSError as e:
            logger.error(f"Error removing state file {db_file}: {e}")
            
    asyncio.run(main())
