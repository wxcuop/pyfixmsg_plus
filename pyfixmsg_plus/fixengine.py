import logging
import socket
import threading
from datetime import datetime, timezone
from time import sleep
from fixmessage import FixMessage
from fixeventsnotifier import FIXEventsNotifier
from crypt import crypt, CryptEventsNotifier, CryptException
from timeout import TimeOut
from seq_no_file import SequenceNumberFile

class FIXEException(Exception):
    pass

class FIXEngine(threading.Thread):
    CRYPT_PASS = "fixenginecryptpassword"
    FIX_Head = f"8=FIX.4.2{FixMessage.c_FixSep}9="

    def __init__(self, en, host, service, heartbeat, sender_comp_id, target_comp_id, seq_num_file, initiator, check_user_password):
        super().__init__()
        self.m_logger = logging.getLogger(self.__class__.__name__)
        self.EN = en
        self.CEN = CryptEventsNotifier(self)
        self.FLAG_modeInitiator = initiator
        self.FIXHost = host
        self.FIXService = service
        self.FLAG_CheckSeqnumReceived = True
        self.FP = FixMessage()
        self.FP.f108_HeartBtInt = heartbeat
        self.FP.f49_SenderCompID = sender_comp_id
        self.FP.f56_TargetCompID = target_comp_id
        self.SeqNumFileOut = SequenceNumberFile(SequenceNumberFile.TYPE.NUMBER_OUT, self.EN, f"{seq_num_file}Out.dat")
        self.SeqNumFileIn = SequenceNumberFile(SequenceNumberFile.TYPE.NUMBER_IN, self.EN, f"{seq_num_file}In.dat")
        self.FLAG_checkUserPassword = check_user_password
        self.m_socket_connector = SocketConnector(self.EN)
        self.FIXEngineEndConstructor()

    def FIXEngineEndConstructor(self):
        self.fixtools = FIXTools()
        self.timeOut = TimeOut(self, self.m_logger)
        self.m_logger.info("FIX Engine Version 7.3")

    def setCheckSeqNumReceived(self, yesno):
        self.FLAG_CheckSeqnumReceived = yesno

    def checkConfigFile(self, config):
        RCF = ReadConfigFiles()
        try:
            cfg = RCF.ReadConfig(config)
        except IOError as e:
            raise FIXEException(f"Problem reading FixEngine config file {str(e)}")
        if not cfg:
            raise FIXEException("Problem reading FixEngine config file")
        self.checkConfig(cfg)

    def checkConfig(self, cfg):
        self.FP = FixMessage()
        f56 = ""
        f49 = ""
        c = crypt(FIXEngine.CRYPT_PASS, self.CEN)

        if cfg.get("fixengine_mode"):
            if cfg["fixengine_mode"].lower() == "a":
                self.FLAG_modeInitiator = False
                self.m_logger.info("listening for incoming connection")
            else:
                self.FLAG_modeInitiator = True

        if self.FLAG_modeInitiator:
            if not cfg.get("fixengine_host"):
                raise FIXEException("Parameter fixengine_Host missing from configuration file")
            else:
                self.FIXHost = cfg["fixengine_host"]
                self.m_logger.info(f"host = {self.FIXHost}")

        if not cfg.get("fixengine_service"):
            raise FIXEException("Parameter fixengine_Service missing from configuration file")
        else:
            self.FIXService = int(cfg["fixengine_service"])
            self.m_logger.info(f"service = {self.FIXService}")

        if not cfg.get("fixengine_seqnumfile"):
            raise FIXEException("Parameter fixengine_seqnumfile missing from configuration file")

        if not cfg.get("fixengine_fixversion"):
            self.FIX_Head = f"8=FIX.4.2{FixMessage.c_FixSep}9="
        else:
            self.FIX_Head = f"8={cfg['fixengine_fixversion']}{FixMessage.c_FixSep}9="
            self.m_logger.info(f"FIX Version -ie FIXHead used is {self.FIX_Head.replace(FIXTools.c_FixSep, '|')}")

        self.FP.f108_HeartBtInt = cfg.get("fixengine_heartbeat", "30")
        if "fixengine_heartbeat" not in cfg:
            self.m_logger.warn("Parameter HeartBeat missing from configuration file, default 30")
        else:
            self.m_logger.info(f"heartbeat = {cfg['fixengine_heartbeat']}")

        if cfg.get("fixengine_sendtestrequest") and cfg["fixengine_sendtestrequest"].lower() == "n":
            self.FLAG_sendTimeout = False
            self.m_logger.info("Test Requests will not be sent")

        if cfg.get("fixengine_usedb") and cfg["fixengine_usedb"].lower() == "y":
            self.m_logger.info("FIX Messages will be stored in database")
            self.TableSent = cfg["fixengine_dbtableout"]
            self.TableRead = cfg["fixengine_dbtablein"]
            self.DBT = DBTools(cfg["fixengine_dbconffile"])
            self.FLAG_ProcessResend = cfg.get("fixengine_processresend", "n").lower() == "y"
            if self.FLAG_ProcessResend:
                self.m_logger.info("FIX Engine will resend FIX messages on resend request")

        self.FLAG_CheckSeqnumReceived = cfg.get("fixengine_checkseqnumreceived", "n").lower() == "y"
        if self.FLAG_CheckSeqnumReceived:
            self.m_logger.info("FIX Engine will check the sequence number it receives")
        else:
            self.m_logger.info("FIX Engine will NOT check the sequence number it receives")

        self.encryptedCompIDs = cfg.get("fixengine_encryptedcompids", "y").lower() != "n"
        self.FLAG_useCompression = cfg.get("fixengine_usecompression", "n").lower() == "y"
        if self.FLAG_useCompression:
            self.m_logger.info("FIX Message compression in ON!")

        self.testrequesttimeout = int(cfg.get("fixengine_testrequesttimeout", 10))
        self.m_logger.info(f"testrequesttimeout is set to {self.testrequesttimeout}")

        self.HeartBeatExtDelta = int(cfg.get("fixengine_heartbeatextdelta", 10))
        self.m_logger.info(f"HeartBeatExtDelta is set to {self.HeartBeatExtDelta}")

        if not cfg.get("fixengine_sendercompid"):
            raise FIXEException("Parameter fixengine_sendercompid missing from configuration file")
        else:
            f49 = cfg["fixengine_sendercompid"]
            if self.encryptedCompIDs:
                try:
                    self.FP.f49_SenderCompID = c.checkCrypt(f49)
                except CryptException as e:
                    raise FIXEException(f"Crypt issue, {e}")
            else:
                self.FP.f49_SenderCompID = f49

        if not cfg.get("fixengine_targetcompid"):
            raise FIXEException("fixengine_targetcompid parameter missing from configuration file")
        else:
            f56 = cfg["fixengine_targetcompid"]
            if self.encryptedCompIDs:
                try:
                    self.FP.f56_TargetCompID = c.checkCrypt(f56)
                except CryptException as e:
                    raise FIXEException(f"Crypt issue, {e}")
            else:
                self.FP.f56_TargetCompID = f56

        if "clear:" in f49 or "clear:" in f56:
            raise FIXEException("Problem reading FixEngine config file f49.indexOf(clear:)>=0")

        self.fixtools = FIXTools()

        if cfg.get("fixengine_relyontestrequestforendofreset") and cfg["fixengine_relyontestrequestforendofreset"].lower() == "n":
            self.FLAG_relyOnTestRequestForEndOfReset = False

        if self.FLAG_relyOnTestRequestForEndOfReset:
            self.m_logger.info("Engine will rely on the other side sending a testrequest to detect end of resend")
        else:
            self.m_logger.info("Engine will NOT rely on the other side sending a testrequest to detect end of resend")

        self.SeqNumFileOut = SequenceNumberFile(SequenceNumberFile.TYPE.NUMBER_OUT, self.EN, f"{cfg['fixengine_seqnumfile']}Out.dat")
        self.SeqNumFileIn = SequenceNumberFile(SequenceNumberFile.TYPE.NUMBER_IN, self.EN, f"{cfg['fixengine_seqnumfile']}In.dat")

    def setMainFixParameters(self, fp):
        c = crypt(FIXEngine.CRYPT_PASS, self.CEN)
        self.FP = FixMessage()
        try:
            self.FP.f49_SenderCompID = c.checkCrypt(fp.f49_SenderCompID)
        except CryptException as e:
            raise FIXEException(f"setting new FIX parameters failed due to : {e}")
        try:
            self.FP.f56_TargetCompID = c.checkCrypt(fp.f56_TargetCompID)
        except CryptException as e:
            raise FIXEException(f"setting new FIX parameters failed due to : {e}")
        self.FP.f95_RawDataLength = fp.f95_RawDataLength
        self.FP.f96_RawData = fp.f96_RawData
        self.FP.f98_EncryptMethod = fp.f98_EncryptMethod
        self.FP.f108_HeartBtInt = fp.f108_HeartBtInt

    def setFIXConnectionParams(self, host, service, sender_comp_id, target_comp_id, heartbeat):
        if self.FLAG_isLoggedIn:
            raise FIXEException("Server is logged in, can not set new parameters")
        if self.m_socket_connector.isConnectionOpen():
            raise FIXEException("Socket is not closed, can not set new parameters")

        if host:
            self.FIXHost = host
        if service > 0:
            self.FIXService = service
        if sender_comp_id:
            self.FP.f49_SenderCompID = sender_comp_id
        if target_comp_id:
            self.FP.f56_TargetCompID = target_comp_id
        if heartbeat:
            self.FP.f108_HeartBtInt = heartbeat

    def run(self):
        while True:
            if not self.m_socket_connector.isConnectionOpen():
                sleep(0.1)
                continue

            try:
                s_FIX = self.Listen()
            except (IOException, FIXEException) as e:
                self.m_logger.warn(f"Exception while listening : {e}")
                if not self.FLAG_StopListen:
                    self.Stop("within run, Listen threw Exception")
                s_FIX = ""
                break

            if not self.FLAG_StopListen:
                self.LogMessageFIXRecv(s_FIX.replace(FixMessage.c_FixSep, '|'))
                self.timeOut.ResetTimeOut()
                if self.checkFIXChecksum(s_FIX):
                    if self.FLAG_CheckSeqnumReceived and self.fixtools.getField(s_FIX, "35") != "A":
                        if self.checkSeqNumReceived(s_FIX):
                            try:
                                self.ProcessFIX(s_FIX)
                            except FIXEException as e:
                                self.m_logger.error(f"Process FIX exception {e}\nFIX msg\n{s_FIX}")
                    else:
                        try:
                            self.ProcessFIX(s_FIX)
                        except FIXEException as e:
                            self.m_logger.error(f"FIX msg exception {s_FIX}, Exception {e}")
                else:
                    self.m_logger.error(f"Fix Message not valid {s_FIX}")
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
        self.connection_manager.open_connection(self.fix_host, self.fix_service)
        return self.connect_logon_login_password_heartbeat(reset_flag, login, password)
    elif self.fix_service > 0:
        self.connection_manager.begin_listen_socket(int(self.fix_service), self.m_logger)
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
            self.connection_manager.set_socket(socket)
            self.start()
            return True
    else:
        raise FIXEException("FE Socket is None!")

def close_socket(self):
    self.flag_stop_listen = True
    self.flag_stop_send = True
    self.connection_manager.close_connection()

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
    self.connection_manager.stop_listen_incoming_connections(self.m_logger)
    self.flag_is_in_resend = False

def send_fix_message_to_server(self, fix_message, retry_count):
    # Add logic to send the FIX message to the server
    pass

def handle_incoming_message(self, fix_message):
    # Add logic to handle incoming FIX messages from the server
    pass

def process_resend_request(self, start_seq_num, end_seq_num):
    # Add logic to process resend requests
    pass

def process_heartbeat(self):
    # Add logic to process heartbeat messages
    pass

def process_test_request(self):
    # Add logic to process test requests
    pass

def process_logout(self, reason):
    # Add logic to process logout messages
    pass

