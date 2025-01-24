import os
import sys
from datetime import datetime, timedelta
from threading import Thread, Lock
from fixcommon.crypto import CryptEvents, CryptEventsNotifier, crypt, CryptException
from fixtools import FIXTools
from fixcommon.errors import ErrorLevel
from readconfig import ReadConfigFiles
from fixeexception import FIXEException
from fixtool.fixmessage import FixMessage
from fixsessionlevel import SequenceNumberFile, TimeOut, HeartBeat, TYPE
from fixtool.fixeventsnotifier import FIXEventsNotifier
from fixnetwork import SocketConnector, ListenSocket

class DBTools:
    def __init__(self, a):
        pass

    def get_enrich_map_table(self, a, b):
        pass

    def get_stock_mapping_table(self, a, b, c):
        pass

    def store_for_fix(self, table_sent, seq, val):
        pass

    def store_stock_mapping_table(self, mapping):
        pass

class FIXEngine(CryptEvents, Thread):
    CRYPT_PASS = "fixenginecryptpassword"

    def __init__(self, *args):
        super().__init__()
        self.lock = Lock()
        self.m_logger = None  # Replace with appropriate logging mechanism
        self.custom_header_tags = ""
        self.timeout = None
        self.db_tools = None
        self.heartbeat = None
        self.fix_message = None
        self.fix_host = ""
        self.fix_service = None
        self.fix_tools = None
        self.seq_num_file_out = None
        self.seq_num_file_in = None
        self.listen_socket = None
        self.crypt_events_notifier = None
        self.fix_head = f"8=FIX.4.2{FixMessage.c_FixSep}9="
        self.flag_stop_listen = False
        self.flag_stop_send = False
        self.flag_is_logged_in = False
        self.flag_is_stopping = False
        self.encrypted_comp_ids = True
        self.flag_is_in_resend = False
        self.sequence_number_in_during_resend = 0
        self.stored_fix_while_resend = ""
        self.table_read = ""
        self.table_sent = ""
        self.flag_process_resend = False
        self.flag_check_seq_num_received = False
        self.flag_check_user_password = False
        self.flag_mode_initiator = True
        self.flag_use_compression = False
        self.test_request_timeout = 10
        self.flag_send_timeout = True
        self.heartbeat_ext_delta = 10
        self.flag_rely_on_test_request_for_end_of_reset = True
        self.event_notifier = None

        self._parse_args(args)
        self.fix_engine_end_constructor()

    def _parse_args(self, args):
        if isinstance(args[0], FIXEventsNotifier):
            if len(args) == 9:
                self._init_with_9_args(args)
            elif len(args) == 2:
                self._init_with_2_args(args)
            elif len(args) == 0:
                pass
            else:
                raise FIXEException("Bad arguments for constructor of FIXEngine!")
        else:
            raise FIXEException("First argument must be a FIXEventsNotifier instance")

    def _init_with_9_args(self, args):
        en, host, service, heartbeat, sender_comp_id, target_comp_id, sequence_number_file, initiator, check_user_password = args
        self.event_notifier = en
        self.crypt_events_notifier = CryptEventsNotifier(self)
        self.flag_mode_initiator = initiator
        self.fix_host = host
        self.fix_service = service
        self.fix_head = f"8=FIX.4.2{FixMessage.c_FixSep}9="
        self.flag_check_seq_num_received = True
        self.fix_message = FixMessage()
        self.fix_message.f108_HeartBtInt = heartbeat
        self.fix_message.f49_SenderCompID = sender_comp_id
        self.fix_message.f56_TargetCompID = target_comp_id
        self.seq_num_file_out = SequenceNumberFile(TYPE.NUMBER_OUT, self.event_notifier, f"{sequence_number_file}Out.dat")
        self.seq_num_file_in = SequenceNumberFile(TYPE.NUMBER_IN, self.event_notifier, f"{sequence_number_file}In.dat")
        self.flag_check_user_password = check_user_password
        self.m_socket_connector = SocketConnector(self.event_notifier)

    def _init_with_2_args(self, args):
        if isinstance(args[1], FIXEventsNotifier):
            config_file, en = args
            self.event_notifier = en
            self.crypt_events_notifier = CryptEventsNotifier(self)
            self.check_config_file(config_file)
            self.m_socket_connector = SocketConnector(en)
        elif isinstance(args[0], FIXEventsNotifier):
            en, cfg = args
            self.event_notifier = en
            self.crypt_events_notifier = CryptEventsNotifier(self)
            self.check_config(cfg)
            self.m_socket_connector = SocketConnector(en)

    def fix_engine_end_constructor(self):
        self.fix_tools = FIXTools()
        self.timeout = TimeOut(self, self.m_logger)
        self.m_logger.info("FIX Engine Version 7.3")

    def set_check_seq_num_received(self, yes_no):
        self.flag_check_seq_num_received = yes_no

    def check_config_file(self, config):
        self.config_reader = ReadConfigFiles()
        try:
            self.config = self.config_reader.read_config_respect_case(config)
        except IOError as e:
            raise FIXEException(f"Problem reading FixEngine config file {str(e)}")
        if not self.config:
            raise FIXEException("Problem reading FixEngine config file")
        self.check_config(self.config)

    def check_config(self, config):
        self.fix_message = FixMessage()
        crypt_instance = crypt(FIXEngine.CRYPT_PASS, self.crypt_events_notifier)

        self.flag_mode_initiator = config.get("fixengine_mode", "a").lower() != "a"
        if not self.flag_mode_initiator:
            self.m_logger.info("listening for incoming connection")

        self.fix_host = config.get("fixengine_host")
        if self.flag_mode_initiator and not self.fix_host:
            raise FIXEException("Parameter fixengine_Host missing from configuration file")
        if self.fix_host:
            self.m_logger.info(f"host = {self.fix_host}")

        self.fix_service = config.get("fixengine_service")
        if not self.fix_service:
            raise FIXEException("Parameter fixengine_Service missing from configuration file")
        self.fix_service = int(self.fix_service)
        self.m_logger.info(f"service = {self.fix_service}")

        if config.get("fixengine_seqnumfile") is None:
            raise FIXEException("Parameter fixengine_seqnumfile missing from configuration file")

        self.fix_head = f"8={config.get('fixengine_fixversion', 'FIX.4.2')}{FixMessage.c_FixSep}9="
        self.m_logger.info(f"FIX Version -ie FIXHead used is {self.fix_head.replace(FIXTools.c_FixSep, '|')}")

        self.fix_message.f108_HeartBtInt = config.get("fixengine_heartbeat", "30")
        if "fixengine_heartbeat" not in config:
            self.m_logger.warn("Parameter HeartBeat missing from configuration file, default 30")
        else:
            self.m_logger.info(f"heartbeat = {config.get('fixengine_heartbeat')}")

        self.flag_send_timeout = config.get("fixengine_sendtestrequest", "y").lower() != "n"
        if not self.flag_send_timeout:
            self.m_logger.info("Test Requests will not be sent")

        if config.get("fixengine_usedb", "n").lower() == "y":
            self.m_logger.info("FIX Messages will be stored in database")
            self.table_sent = config["fixengine_dbtableout"]
            self.table_read = config["fixengine_dbtablein"]
            self.db_tools = DBTools(config["fixengine_dbconffile"])
            self.flag_process_resend = config.get("fixengine_processresend", "n").lower() == "y"
            if self.flag_process_resend:
                self.m_logger.info("FIX Engine will resend FIX messages on resend request")

        self.flag_check_seq_num_received = config.get("fixengine_checkseqnumreceived", "n").lower() == "y"
        if self.flag_check_seq_num_received:
            self.m_logger.info("FIX Engine will check the sequence number it receives")
        else:
            self.m_logger.info("FIX Engine will NOT check the sequence number it receives")

        self.encrypted_comp_ids = config.get("fixengine_encryptedcompids", "y").lower() != "n"
        self.flag_use_compression = config.get("fixengine_usecompression", "n").lower() == "y"
        if self.flag_use_compression:
            self.m_logger.info("FIX Message compression in ON!")

        self.test_request_timeout = int(config.get("fixengine_testrequesttimeout", 10))
        self.m_logger.info(f"testrequesttimeout is set to {self.test_request_timeout}")

        self.heartbeat_ext_delta = int(config.get("fixengine_heartbeatextdelta", 10))
        self.m_logger.info(f"HeartBeatExtDelta is set to {self.heartbeat_ext_delta}")

        sender_comp_id = config.get("fixengine_sendercompid")
        if sender_comp_id is None:
            raise FIXEException("Parameter fixengine_sendercompid missing from configuration file")
        if self.encrypted_comp_ids:
            try:
                self.fix_message.f49_SenderCompID = crypt_instance.check_crypt(sender_comp_id)
            except CryptException as e:
                raise FIXEException(f"Crypt issue, {str(e)}")
        else:
            self.fix_message.f49_SenderCompID = sender_comp_id

        target_comp_id = config.get("fixengine_targetcompid")
        if target_comp_id is None:
            raise FIXEException("fixengine_targetcompid parameter missing from configuration file")
        if self.encrypted_comp_ids:
            try:
                self.fix_message.f56_TargetCompID = crypt_instance.check_crypt(target_comp_id)
            except CryptException as e:
                raise FIXEException(f"Crypt issue, {str(e)}")
        else:
            self.fix_message.f56_TargetCompID = target_comp_id

        if "clear:" in sender_comp_id or "clear:" in target_comp_id:
            raise FIXEException("Problem reading FixEngine config file f49.indexOf(clear:)>=0")

        self.fix_tools = FIXTools()
        self.flag_rely_on_test_request_for_end_of_reset = config.get("fixengine_relyontestrequestforendofreset", "y").lower() == "y"
        if self.flag_rely_on_test_request_for_end_of_reset:
            self.m_logger.info("Engine will rely on the other side sending a testrequest to detect end of resend")
        else:
            self.m_logger.info("Engine will NOT rely on the other side sending a testrequest to detect end of resend")

        if config.get("fixengine_seqnumfile") is None:
            raise FIXEException("fixengine_seqnumfile parameter is missing")

        self.seq_num_file_out = SequenceNumberFile(TYPE.NUMBER_OUT, self.event_notifier, f"{config.get('fixengine_seqnumfile')}Out.dat")
        self.seq_num_file_in = SequenceNumberFile(TYPE.NUMBER_IN, self.event_notifier, f"{config.get('fixengine_seqnumfile')}In.dat")

    def set_main_fix_parameters(self, fix_params):
        crypt_instance = crypt(FIXEngine.CRYPT_PASS, self.crypt_events_notifier)
        self.fix_message = FixMessage()
        try:
            self.fix_message.f49_SenderCompID = crypt_instance.check_crypt(fix_params.f49_SenderCompID)
        except CryptException as e:
            raise FIXEException(f"setting FIX parameters failed due to: {str(e)}")

        try:
            self.fix_message.f56_TargetCompID = crypt_instance.check_crypt(fix_params.f56_TargetCompID)
        except CryptException as e:
            raise FIXEException(f"setting FIX parameters failed due to: {str(e)}")

        self.fix_message.f95_RawDataLength = fix_params.f95_RawDataLength
        self.fix_message.f96_RawData = fix_params.f96_RawData
        self.fix_message.f98_EncryptMethod = fix_params.f98_EncryptMethod
        self.fix_message.f108_HeartBtInt = fix_params.f108_HeartBtInt

    def set_fix_connection_params(self, host, service, sender_comp_id, target_comp_id, heartbeat):
        if self.flag_is_logged_in:
            raise FIXEException("Server is logged in, cannot set parameters")

        if self.m_socket_connector.is_connection_open():
            raise FIXEException("Socket is not closed, cannot set parameters")

        if host:
            self.fix_host = host
        if service > 0:
            self.fix_service = service
        if sender_comp_id:
            self.fix_message.f49_SenderCompID = sender_comp_id
        if target_comp_id:
            self.fix_message.f56_TargetCompID = target_comp_id
        if heartbeat:
            self.fix_message.f108_HeartBtInt = heartbeat

    def start_engine(self, seq_num_out, seq_num_in, reset_flag, login="", password=""):
        self.flag_is_stopping = False
        self.flag_stop_send = False
        self.flag_stop_listen = False
        self.flag_is_stopping = False

        if seq_num_out > -1:
            self.seq_num_file_out.set_sequential_number(seq_num_out)
        if seq_num_in > -1:
            self.seq_num_file_in.set_sequential_number(seq_num_in)

        self.m_logger.info(f"Starting FIXEngine with SeqNum OUT = {self.seq_num_file_out.get_sequential_number()}")
        self.m_logger.info(f"Starting FIXEngine with SeqNum IN = {self.seq_num_file_in.get_sequential_number()}")

        if self.flag_mode_initiator:
            self.m_socket_connector.open_connection(self.fix_host, self.fix_service)
            return self.connect_logon_login_password_heartbeat(reset_flag, login, password)
        elif self.fix_service > 0:
            self.begin_listen_socket(int(self.fix_service))
        else:
            raise FIXEException("Listening port invalid")
        return True

    def start_with_existing_socket(self, seq_num_out, seq_num_in, reset_flag, socket, login="", password=""):
        self.flag_is_stopping = False
        self.flag_stop_send = False
        self.flag_stop_listen = False
        self.flag_is_stopping = False

        if seq_num_out > -1:
            self.seq_num_file_out.set_sequential_number(seq_num_out)
        if seq_num_in > -1:
            self.seq_num_file_in.set_sequential_number(seq_num_in)

        self.m_logger.info(f"Starting FIXEngine with SeqNum OUT = {self.seq_num_file_out.get_sequential_number()}")
        self.m_logger.info(f"Starting FIXEngine with SeqNum IN = {self.seq_num_file_in.get_sequential_number()}")

        if socket is not None:
            if self.flag_mode_initiator:
                self.m_logger.info(f"Starting FIXEngine in initiator mode with existing socket, check UserPassword is {self.flag_check_user_password}")
                return self.connect_logon_login_password_heartbeat(reset_flag, login, password)
            else:
                self.m_logger.info(f"Starting FIXEngine in acceptor mode with existing socket, check UserPassword is {self.flag_check_user_password}")
                self.m_socket_connector.set_socket(socket)
                self.start()
                return True
        else:
            raise FIXEException("FE Socket is None!")

    def begin_listen_socket(self, service):
        self.listen_socket = ListenSocket(service, self, self.m_logger)
        self.listen_socket.start()  # throws FIXEException if fails
        self.start()

    def stop_listen_incoming_connections(self):
        if self.listen_socket is not None:
            try:
                self.listen_socket.stop()
            except FIXEException as e:
                self.m_logger.warn(f"Exception while stopping the listen socket {str(e)}")

    def close_socket(self):
        self.flag_stop_listen = True
        self.flag_stop_send = True
        self.m_socket_connector.close_connection()

        wait = 0
        while self.flag_is_logged_in and wait < 25:
            wait += 1
            try:
                Thread.sleep(100)
            except Exception:
                pass  # sleep to get logout ack

        if self.flag_is_logged_in:
            self.flag_is_logged_in = False
            self.m_logger.info("logged out status has been forced - ie client did not answer")

    def connect_logon_login_password_heartbeat(self, reset_flag, login, password):
        self.login(self.fix_message, reset_flag, login, password)
        wait = 0
        while not self.flag_is_logged_in and wait < 50:
            wait += 1
            try:
                Thread.sleep(100)
            except InterruptedException:
                pass

        if self.flag_is_logged_in:
            self.heartbeat = HeartBeat(self, self.fix_message)
            self.heartbeat.start()
            return True
        else:
            return False

    def login(self, fix_message, reset_flag, login, password):
        if self.flag_mode_initiator:  # otherwise, we are already listening...
            self.start()
        fix = FixMessage()
        fix.f108_HeartBtInt = fix_message.f108_HeartBtInt
        fix.f35_MsgType = "A"
        fix.f49_SenderCompID = fix_message.f49_SenderCompID
        fix.f56_TargetCompID = fix_message.f56_TargetCompID
        fix.f95_RawDataLength = self.fix_message.f95_RawDataLength
        fix.f96_RawData = self.fix_message.f96_RawData
        fix.f553_UserName = login
        fix.f554_Password = password
        fix.f98_EncryptMethod = self.fix_message.f98_EncryptMethod or "0"

        if reset_flag:
            self.m_logger.info("connecting with reset asked")
            fix.f141_ResetSeqNumFlag = "Y"
        if not self.send_fix_message_to_server(fix, 0):
            self.m_logger.error("issue sending login FixMessage")

    def stop_hb_logout(self, reason):
        if self.heartbeat is not None:
            self.heartbeat.stop()
        fix = FixMessage()
        fix.f35_MsgType = "5"
        fix.f49_SenderCompID = self.fix_message.f49_SenderCompID
        fix.f56_TargetCompID = self.fix_message.f56_TargetCompID
        fix.f58_Text = reason
        self.send_fix_message_to_server(fix, 0)

    def stop_engine(self, reason="", issue=0):
        if self.flag_is_stopping:
            self.m_logger.info(f"stop requested while already stopping..., {reason}")
            return

        self.m_logger.info(f"Stopping Fix Engine, {reason}")
        self.flag_is_stopping = True
        self.stop_hb_logout(reason)
        self.stop_listen
