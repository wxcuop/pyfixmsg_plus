# At the beginning of examples/cli_initiator.py
# import sys
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


# print(f"DEBUG_INITIATOR_SCRIPT: Current working directory: {os.getcwd()}", flush=True)
# print(f"DEBUG_INITIATOR_SCRIPT: sys.path = {sys.path}", flush=True)
# print(f"DEBUG_INITIATOR_SCRIPT: pyfixmsg module loaded from: {pyfixmsg_path}", flush=True)
# print(f"DEBUG_INITIATOR_SCRIPT: pyfixmsg version (if defined): {pyfixmsg_version}", flush=True)


import asyncio
import logging
import datetime 
from pyfixmsg_plus.fixengine.configmanager import ConfigManager
from pyfixmsg_plus.fixengine.engine import FixEngine
from pyfixmsg_plus.idgen.id_generator import YMDClOrdIdGenerator
from sample_application import DummyApplication, run_common_initiator_logic

# Basic logging setup for the example
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

async def main():
    config_file = os.environ.get("FIX_CONFIG", "examples/initiator.cfg")
    config_manager = ConfigManager(config_file)
    clordid_generator = YMDClOrdIdGenerator()

    app = DummyApplication()
    engine = await FixEngine.create(config_manager, app)
    app.set_engine(engine)

    await engine.initialize()
    await engine.connect()

    try:
        # Use the shared logic for initiator test flow
        await run_common_initiator_logic(engine, clordid_generator, logger)
        logger.info("Initiator example loop finished. Final engine state: %s", engine.state_machine.state.name if engine and hasattr(engine, 'state_machine') else 'UNKNOWN')
    except KeyboardInterrupt:
        logger.info("Initiator shutting down due to KeyboardInterrupt...")
    except ConnectionRefusedError:
        logger.error(f"Connection refused when trying to connect to {engine.host if engine else 'UNKNOWN_HOST'}:{engine.port if engine else 'UNKNOWN_PORT'}. Ensure acceptor is running.")
    except Exception as e:
        logger.error(f"Error in initiator: {e}", exc_info=True)
    finally:
        if engine and hasattr(engine, 'state_machine') and engine.state_machine.state.name != 'DISCONNECTED':
            logger.info("Ensuring initiator engine is disconnected (final check)...")
            await engine.disconnect(graceful=False)
        logger.info("Initiator main function finished.")

if __name__ == "__main__":
    script_dir_for_config = os.path.dirname(__file__)
    initiator_config_file = os.path.join(script_dir_for_config, 'config_initiator.ini')

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
        default_cfg_writer.set('FIX', 'reset_seq_num_on_logon', 'true')
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
