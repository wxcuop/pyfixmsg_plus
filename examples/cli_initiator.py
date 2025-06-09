import asyncio
import logging
import os
import datetime # Ensure this import is present
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine
from pyfixmsg_plus.fixengine.app import Application # Assuming your base Application class

# Basic logging setup for the example
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class DummyApplication(Application):
    def __init__(self):
        self.engine = None # Will be set by FixEngine

    async def onLogon(self, message, session_id):
        logger.info(f"[{session_id}] Initiator App: Logon successful. Message: {message.to_wire(pretty=True)}")

    async def onLogout(self, message, session_id):
        logger.info(f"[{session_id}] Initiator App: Logout. Message: {message.to_wire(pretty=True)}")

    async def onMessage(self, message, session_id):
        logger.info(f"[{session_id}] Initiator App: Received message type {message.get(35)}: {message.to_wire(pretty=True)}")

    # Method for the FixEngine to set itself on the application
    def set_engine(self, engine):
        self.engine = engine

async def main():
    # Determine the path to the config file relative to this script
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config_initiator.ini') # Use a separate config for initiator
    
    config = ConfigManager(config_path)
    # Ensure required settings are in config_initiator.ini or set them here if needed
    # Example values - these should ideally be in config_initiator.ini
    # config.set('FIX', 'mode', 'initiator')
    # config.set('FIX', 'sender', 'INITIATOR_CLIENT')
    # config.set('FIX', 'target', 'ACCEPTOR_SERVER')
    # config.set('FIX', 'host', '127.0.0.1')
    # config.set('FIX', 'port', '5000') 
    # config.set('FIX', 'heartbeat_interval', '30')
    # config.set('FIX', 'spec_filename', 'FIX44.xml') 
    # config.set('FIX', 'state_file', os.path.join(script_dir, 'initiator_fix_state.db'))


    app = DummyApplication()
    engine = FixEngine(config, app)
    app.set_engine(engine) # Allow app to access engine for sending messages
    
    try:
        logger.info(f"Starting initiator engine (Sender: {engine.sender}, Target: {engine.target}) to connect to {engine.host}:{engine.port}...")
        
        asyncio.create_task(engine.start()) 
        
        logger.info("Initiator engine.start() called. Session establishment in progress.")
        
        sent_test_order = False
        while True: # Main loop to keep alive and monitor
            # Ensure engine and state_machine are initialized before accessing
            if not engine or not hasattr(engine, 'state_machine'):
                await asyncio.sleep(0.1) # Wait briefly if engine is not ready
                continue

            current_state = engine.state_machine.state.name
            if current_state == 'DISCONNECTED':
                if hasattr(engine, 'retry_attempts') and hasattr(engine, 'max_retries') and \
                   engine.max_retries > 0 and engine.retry_attempts >= engine.max_retries:
                    logger.warning(f"Max retries ({engine.max_retries}) reached. Engine remains disconnected. Exiting example loop.")
                else:
                    logger.info("Engine is disconnected. Exiting example loop.")
                break # Exit while loop if disconnected

            if current_state == 'ACTIVE' and not sent_test_order:
                logger.info(f"Session is ACTIVE. Attempting to send a test NewOrderSingle in 3 seconds...")
                await asyncio.sleep(3) 
                if engine.state_machine.state.name == 'ACTIVE': 
                    test_order = engine.fixmsg({
                        35: 'D',    
                        11: f'TestOrd-{datetime.datetime.utcnow().strftime("%H%M%S%f")}', 
                        55: 'MSFT', 
                        54: '1',    
                        38: '100',  
                        40: '1',    
                        44: '150.00' 
                    })
                    logger.info(f"Sending test NewOrderSingle: {test_order.to_wire(pretty=True)}")
                    await engine.send_message(test_order)
                    sent_test_order = True 
                else:
                    logger.info(f"State changed from ACTIVE to {engine.state_machine.state.name} before sending test order.")
            
            await asyncio.sleep(1)

        logger.info(f"Initiator example loop finished. Final engine state: {engine.state_machine.state.name if engine and hasattr(engine, 'state_machine') else 'UNKNOWN'}")

    except KeyboardInterrupt:
        logger.info("Initiator shutting down due to KeyboardInterrupt...")
    except ConnectionRefusedError:
        logger.error(f"Connection refused when trying to connect to {engine.host if engine else 'UNKNOWN_HOST'}:{engine.port if engine else 'UNKNOWN_PORT'}. Ensure acceptor is running.")
    except Exception as e:
        logger.error(f"Error in initiator: {e}", exc_info=True)
    finally:
        # Ensure this line (110 or adjusted) is exactly as follows:
        if engine and hasattr(engine, 'state_machine') and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring initiator engine is disconnected...")
            await engine.disconnect(graceful=True) 
        logger.info("Initiator main function finished.")

if __name__ == "__main__":
    script_dir_for_config = os.path.dirname(__file__)
    initiator_config_file = os.path.join(script_dir_for_config, 'config_initiator.ini')
    
    if not os.path.exists(initiator_config_file):
        default_cfg = ConfigManager(initiator_config_file) 
        default_cfg.set('FIX', 'mode', 'initiator')
        default_cfg.set('FIX', 'sender', 'INITIATOR_CLIENT') 
        default_cfg.set('FIX', 'target', 'ACCEPTOR_SERVER') 
        default_cfg.set('FIX', 'version', 'FIX.4.4')
        default_cfg.set('FIX', 'spec_filename', 'FIX44.xml') 
        default_cfg.set('FIX', 'host', '127.0.0.1')
        default_cfg.set('FIX', 'port', '5000')
        default_cfg.set('FIX', 'heartbeat_interval', '30')
        default_cfg.set('FIX', 'retry_interval', '5')
        default_cfg.set('FIX', 'max_retries', '3') # Set a value for max_retries
        default_cfg.set('FIX', 'state_file', os.path.join(script_dir_for_config, 'initiator_fix_state.db'))
        default_cfg.set('FIX', 'reset_seq_num_on_logon', 'false')
        default_cfg.save() 
        logger.info(f"Created default initiator config: {initiator_config_file}")

    db_path_config_init = ConfigManager(initiator_config_file)
    db_file_init = db_path_config_init.get('FIX', 'state_file', os.path.join(script_dir_for_config, 'initiator_fix_state.db'))
    if os.path.exists(db_file_init):
        try:
            os.remove(db_file_init)
            logger.info(f"Removed previous initiator state file: {db_file_init}")
        except OSError as e:
            logger.error(f"Error removing initiator state file {db_file_init}: {e}")

    asyncio.run(main())
