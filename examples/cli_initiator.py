import asyncio
import logging
import os
import datetime 
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine
from pyfixmsg_plus.application import Application 

# Basic logging setup for the example
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class DummyApplication(Application):
    def __init__(self):
        self.engine = None 
        super().__init__() 

    def set_engine(self, engine): 
        self.engine = engine

    async def onCreate(self, sessionID):
        self.logger.info(f"[{sessionID}] Initiator App: onCreate")

    async def onLogon(self, sessionID, message=None): 
        self.logger.info(f"[{sessionID}] Initiator App: Logon successful.")
        if message and hasattr(message, 'to_wire'):
            self.logger.info(f"Logon Message: {message.to_wire(pretty=True)}")

    async def onLogout(self, sessionID, message=None): 
        self.logger.info(f"[{sessionID}] Initiator App: Logout.")
        if message and hasattr(message, 'to_wire'):
            self.logger.info(f"Logout Message: {message.to_wire(pretty=True)}")

    async def toAdmin(self, message, sessionID):
        self.logger.debug(f"[{sessionID}] Initiator App toAdmin: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def fromAdmin(self, message, sessionID):
        self.logger.debug(f"[{sessionID}] Initiator App fromAdmin: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def toApp(self, message, sessionID):
        self.logger.debug(f"[{sessionID}] Initiator App toApp: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def fromApp(self, message, sessionID):
        self.logger.debug(f"[{sessionID}] Initiator App fromApp: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def onMessage(self, message, sessionID):
        self.logger.info(f"[{sessionID}] Initiator App: Received message type {message.get(35) if hasattr(message, 'get') else 'Unknown'}: {message.to_wire(pretty=True) if hasattr(message, 'to_wire') else str(message)}")


async def main():
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config_initiator.ini') 
    
    # When ConfigManager is instantiated here, it will use 'config_initiator.ini'
    # due to the Singleton behavior, if this is the first instantiation in this process
    # with this specific path, it will stick.
    config = ConfigManager(config_path) 
    
    app = DummyApplication()
    engine = FixEngine(config, app) 
    # The FixEngine should ideally call app.set_engine(self)
    # If not, this manual call is okay for the example.
    if hasattr(app, 'set_engine'):
        app.set_engine(engine) 
    
    try:
        logger.info(f"Starting initiator engine (Sender: {engine.sender}, Target: {engine.target}) to connect to {engine.host}:{engine.port}...")
        
        asyncio.create_task(engine.start()) 
        
        logger.info("Initiator engine.start() called. Session establishment in progress.")
        
        sent_test_order = False
        while True: 
            if not engine or not hasattr(engine, 'state_machine'):
                await asyncio.sleep(0.1) 
                continue

            current_state = engine.state_machine.state.name
            if current_state == 'DISCONNECTED':
                if hasattr(engine, 'retry_attempts') and hasattr(engine, 'max_retries') and \
                   engine.max_retries > 0 and engine.retry_attempts >= engine.max_retries:
                    logger.warning(f"Max retries ({engine.max_retries}) reached. Engine remains disconnected. Exiting example loop.")
                else:
                    logger.info("Engine is disconnected. Exiting example loop.")
                break 

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
        if engine and hasattr(engine, 'state_machine') and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring initiator engine is disconnected...")
            await engine.disconnect(graceful=True) 
        logger.info("Initiator main function finished.")

if __name__ == "__main__":
    script_dir_for_config = os.path.dirname(__file__)
    initiator_config_file = os.path.join(script_dir_for_config, 'config_initiator.ini')
    
    # This ConfigManager instance is specifically for creating/updating the default config file.
    # The Singleton pattern means it might be the same instance as used in main(),
    # but its config_path will be set based on the first call with a path.
    if not os.path.exists(initiator_config_file):
        default_cfg_writer = ConfigManager(initiator_config_file) # Explicitly pass path
        default_cfg_writer.set('FIX', 'mode', 'initiator')
        default_cfg_writer.set('FIX', 'sender', 'INITIATOR_CLIENT') 
        default_cfg_writer.set('FIX', 'target', 'ACCEPTOR_SERVER') 
        default_cfg_writer.set('FIX', 'version', 'FIX.4.4')
        default_cfg_writer.set('FIX', 'spec_filename', 'FIX44.xml') 
        default_cfg_writer.set('FIX', 'host', '127.0.0.1')
        default_cfg_writer.set('FIX', 'port', '5000')
        default_cfg_writer.set('FIX', 'heartbeat_interval', '30')
        default_cfg_writer.set('FIX', 'retry_interval', '5')
        default_cfg_writer.set('FIX', 'max_retries', '3') 
        default_cfg_writer.set('FIX', 'state_file', os.path.join(script_dir_for_config, 'initiator_fix_state.db'))
        default_cfg_writer.set('FIX', 'reset_seq_num_on_logon', 'false')
        default_cfg_writer.save_config() # CORRECTED METHOD NAME
        logger.info(f"Created default initiator config: {initiator_config_file}")

    # This ConfigManager is for reading the path to the DB file for cleanup.
    # It will use the initiator_config_file path.
    db_path_reader = ConfigManager(initiator_config_file)
    db_file_init = db_path_reader.get('FIX', 'state_file', os.path.join(script_dir_for_config, 'initiator_fix_state.db'))
    if os.path.exists(db_file_init):
        try:
            os.remove(db_file_init)
            logger.info(f"Removed previous initiator state file: {db_file_init}")
        except OSError as e:
            logger.error(f"Error removing initiator state file {db_file_init}: {e}")

    asyncio.run(main())
