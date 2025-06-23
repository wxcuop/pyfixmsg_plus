# At the beginning of examples/cli_initiator.py
import sys
import os # Add this import

# Try to import pyfixmsg early to check its path
try:
    import pyfixmsg
    pyfixmsg_path = os.path.abspath(pyfixmsg.__file__)
    pyfixmsg_version = getattr(pyfixmsg, '__version__', 'N/A')
except ImportError as e:
    pyfixmsg_path = f"Error importing pyfixmsg: {e}"
    pyfixmsg_version = "N/A"
except AttributeError: # If pyfixmsg is a namespace package or __file__ is not set
    pyfixmsg_path = "pyfixmsg.__file__ not found (possibly a namespace package or an issue)"
    pyfixmsg_version = getattr(pyfixmsg, '__version__', 'N/A')


print(f"DEBUG_INITIATOR_SCRIPT: Current working directory: {os.getcwd()}", flush=True)
print(f"DEBUG_INITIATOR_SCRIPT: sys.path = {sys.path}", flush=True)
print(f"DEBUG_INITIATOR_SCRIPT: pyfixmsg module loaded from: {pyfixmsg_path}", flush=True)
print(f"DEBUG_INITIATOR_SCRIPT: pyfixmsg version (if defined): {pyfixmsg_version}", flush=True)


import asyncio
import logging
import os
import datetime 
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine
from pyfixmsg_plus.application import Application 

# Basic logging setup for the example
logging.basicConfig(
    level=logging.DEBUG, # <--- Ensure this is DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # handlers=[
    #     logging.StreamHandler() # To see logs in console if running locally
    # ]
)
logger = logging.getLogger(__name__)

class DummyApplication(Application):
    def __init__(self):
        self.engine = None 
        if hasattr(super(), '__init__'):
             super().__init__()
        # self.logger = logging.getLogger(self.__class__.__name__)


    def set_engine(self, engine): 
        self.engine = engine
        # self.logger.info("Engine set on Initiator DummyApplication.")

    async def onCreate(self, sessionID):
        # self.logger.info(f"[{sessionID}] Initiator App: onCreate")
        pass

    async def onLogon(self, sessionID, message=None): 
        # self.logger.info(f"[{sessionID}] Initiator App: Logon successful.")
        if message and hasattr(message, 'to_wire'):
            pass
            # self.logger.info(f"Logon Message: {message.to_wire(pretty=True)}")

    async def onLogout(self, sessionID, message=None): 
        # self.logger.info(f"[{sessionID}] Initiator App: Logout.")
        if message and hasattr(message, 'to_wire'):
            pass
            # self.logger.info(f"Logout Message: {message.to_wire(pretty=True)}")

    async def toAdmin(self, message, sessionID):
        # self.logger.debug(f"[{sessionID}] Initiator App toAdmin: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def fromAdmin(self, message, sessionID):
        # self.logger.debug(f"[{sessionID}] Initiator App fromAdmin: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def toApp(self, message, sessionID):
        # self.logger.debug(f"[{sessionID}] Initiator App toApp: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def fromApp(self, message, sessionID):
        # self.logger.debug(f"[{sessionID}] Initiator App fromApp: MsgType {message.get(35) if hasattr(message, 'get') else 'Unknown'}")
        return message 

    async def onMessage(self, message, sessionID):
        msg_type = message.get(35) if hasattr(message, 'get') else "Unknown"
        logger.info(f"[{sessionID}] Initiator App: Received message type {msg_type}: {message.to_wire(pretty=True) if hasattr(message, 'to_wire') else str(message)}")


async def main():
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config_initiator.ini') 
    
    config = ConfigManager(config_path) 
    
    app = DummyApplication()
    engine = FixEngine(config, app) 
    if hasattr(app, 'set_engine'):
        app.set_engine(engine) 
    
    engine_task = None
    try:
        logger.info(f"Starting initiator engine (Sender: {engine.sender}, Target: {engine.target}) to connect to {engine.host}:{engine.port}...")
        
        engine_task = asyncio.create_task(engine.start()) 
        
        logger.info("Initiator engine.start() task created. Allowing time for connection attempt...")
        
        # Give the engine a moment to attempt connection and change state
        # This is a simple way; a more robust way might involve waiting for a specific state event
        await asyncio.sleep(2) # Increased initial delay to 2 seconds

        sent_test_order = False
        loop_count = 0
        max_loops_disconnected = 5 # Exit if disconnected for ~5 seconds after initial wait

        while True: 
            loop_count +=1
            if not engine or not hasattr(engine, 'state_machine'):
                logger.warning("Engine or state_machine not available yet, sleeping...")
                await asyncio.sleep(1) 
                continue

            current_state = engine.state_machine.state.name
            logger.debug(f"Main loop check: Engine state is {current_state}")

            if current_state == 'DISCONNECTED':
                if loop_count > max_loops_disconnected : # Only break if it's persistently disconnected after initial attempts
                    logger.info(f"Engine is persistently DISCONNECTED after {loop_count} checks. Exiting example loop.")
                    if hasattr(engine, 'retry_attempts') and hasattr(engine, 'max_retries') and \
                       engine.max_retries > 0 and engine.retry_attempts >= engine.max_retries:
                        logger.warning(f"Max retries ({engine.max_retries}) also reached.")
                    break 
                else:
                    logger.info(f"Engine is DISCONNECTED (check {loop_count}/{max_loops_disconnected}). Will check again.")


            if current_state == 'ACTIVE' and not sent_test_order:
                logger.info(f"Session is ACTIVE. Attempting to send a test NewOrderSingle in 1 second...")
                await asyncio.sleep(1) # Shorter delay once active
                if engine.state_machine.state.name == 'ACTIVE': 
                    test_order = engine.fixmsg({
                        35: 'D',    
                        11: f'TestOrd-{datetime.datetime.utcnow().strftime("%H%M%S%f")}', 
                        55: 'MSFT', 
                        54: '1',    
                        38: '100',  
                        40: '1',    
                        44: '150.00',
                        60: datetime.datetime.utcnow().strftime('%Y%m%d-%H:%M:%S.%f')[:-3]       
                    })
                    logger.info(f"Sending test NewOrderSingle: {str(test_order)}")
                    await engine.send_message(test_order)
                    sent_test_order = True 
                    # After sending, let's wait a bit then initiate disconnect for the example
                    await asyncio.sleep(5)
                    logger.info("Test order sent. Initiating graceful disconnect.")
                    await engine.disconnect(graceful=True) # This will eventually lead to DISCONNECTED state and loop exit
                else:
                    logger.info(f"State changed from ACTIVE to {engine.state_machine.state.name} before sending test order.")
            
            if engine_task and engine_task.done():
                logger.info("Engine task has completed. Exiting main loop.")
                try:
                    engine_task.result() # To raise any exceptions from the engine task
                except Exception as e_task:
                    logger.error(f"Exception from engine task: {e_task}", exc_info=True)
                break

            await asyncio.sleep(1)

        logger.info(f"Initiator example loop finished. Final engine state: {engine.state_machine.state.name if engine and hasattr(engine, 'state_machine') else 'UNKNOWN'}")

    except KeyboardInterrupt:
        logger.info("Initiator shutting down due to KeyboardInterrupt...")
    except ConnectionRefusedError:
        logger.error(f"Connection refused when trying to connect to {engine.host if engine else 'UNKNOWN_HOST'}:{engine.port if engine else 'UNKNOWN_PORT'}. Ensure acceptor is running.")
    except Exception as e:
        logger.error(f"Error in initiator: {e}", exc_info=True)
    finally:
        if engine_task and not engine_task.done():
            logger.info("Cancelling engine task...")
            engine_task.cancel()
            try:
                await engine_task
            except asyncio.CancelledError:
                logger.info("Engine task successfully cancelled.")
            except Exception as e_task_cancel:
                 logger.error(f"Exception while cancelling engine task: {e_task_cancel}", exc_info=True)


        if engine and hasattr(engine, 'state_machine') and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring initiator engine is disconnected (final check)...")
            await engine.disconnect(graceful=False) # Force disconnect if still not done
        
        logger.info("Initiator main function finished.")

if __name__ == "__main__":
    script_dir_for_config = os.path.dirname(__file__)
    initiator_config_file = os.path.join(script_dir_for_config, 'config_initiator.ini')

# [default]
# FileStorePath=target/data/executor
# ConnectionType=acceptor
# StartTime=00:00:00
# EndTime=00:00:00
# HeartBtInt=30
# ValidOrderTypes=1,2,F
# SenderCompID=EXEC
# TargetCompID=BANZAI
# UseDataDictionary=Y
# DefaultMarketPrice=12.30

# [session]
# BeginString=FIX.4.0
# SocketAcceptPort=9876

# [session]
# BeginString=FIX.4.1
# SocketAcceptPort=9877

# [session]
# BeginString=FIX.4.2
# SocketAcceptPort=9878

# [session]
# BeginString=FIX.4.3
# SocketAcceptPort=9879

# [session]
# BeginString=FIX.4.4
# SocketAcceptPort=9880

# [session]
# BeginString=FIXT.1.1
# DefaultApplVerID=FIX.5.0
# SocketAcceptPort=9881
    
    if not os.path.exists(initiator_config_file):
        default_cfg_writer = ConfigManager(initiator_config_file) 
        default_cfg_writer.set('FIX', 'mode', 'initiator')
        default_cfg_writer.set('FIX', 'sender', 'BANZAI') 
        default_cfg_writer.set('FIX', 'target', 'EXEC') 
        default_cfg_writer.set('FIX', 'version', 'FIX.4.4')
        default_cfg_writer.set('FIX', 'spec_filename', 'FIX44.xml') 
        default_cfg_writer.set('FIX', 'host', '127.0.0.1')
        default_cfg_writer.set('FIX', 'port', '9880')
        default_cfg_writer.set('FIX', 'heartbeat_interval', '30')
        default_cfg_writer.set('FIX', 'retry_interval', '5')
        default_cfg_writer.set('FIX', 'max_retries', '3') 
        default_cfg_writer.set('FIX', 'state_file', os.path.join(script_dir_for_config, 'initiator_fix_state.db'))
        default_cfg_writer.set('FIX', 'reset_seq_num_on_logon', 'false')
        default_cfg_writer.set('FIX', 'EncryptMethod', '0')
        default_cfg_writer.save_config() 
        logger.info(f"Created default initiator config: {initiator_config_file}")

    db_path_reader = ConfigManager(initiator_config_file)
    db_file_init = db_path_reader.get('FIX', 'state_file', os.path.join(script_dir_for_config, 'initiator_fix_state.db'))
    if os.path.exists(db_file_init):
        try:
            os.remove(db_file_init)
            logger.info(f"Removed previous initiator state file: {db_file_init}")
        except OSError as e:
            logger.error(f"Error removing initiator state file {db_file_init}: {e}")

    asyncio.run(main())
