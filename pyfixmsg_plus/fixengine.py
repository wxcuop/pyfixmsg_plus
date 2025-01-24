from fixcommon.crypto import CryptEvents,CryptEventsNotifier,crypt,CryptException
from fixtools import FIXTools
from fixcommon.errors import ErrorLevel
from readconfig import ReadConfigFiles
#from org.apache.log4j import Logger
from fixeexception import FIXEException
from java.lang import Runnable,Thread,InterruptedException,NumberFormatException
from java.io import IOException
from java.lang import String as jString
from java.util import TimeZone,GregorianCalendar
from java.text import SimpleDateFormat
from fixtool.fixmessage import FixMessage
from fixsessionlevel import SequenceNumberFile,TimeOut,HeartBeat,TYPE
from fixtool.fixeventsnotifier import FIXEventsNotifier
from fixnetwork import SocketConnector,ListenSocket
from threading import Lock
import jarray
from org.apache.log4j import Logger

class dbtools:
    def __init__(self,a):
        pass
    def GetEnrichMapTable(self,a,b):
        pass
    def GetStockMappingTable(self,a,b,c):
        pass
    def StoreForFix(self,TableSent,seq,val):
        pass
    def StoreStockMappingTable(self,mapping):
        pass
    
    
class FIXEngine(CryptEvents,Runnable):
    CRYPTPass = "fixenginecryptpassword"
    
    def setCheckSeqNumReceived(self,yesno):
        self.FLAG_CheckSeqnumReceived=yesno
        
    def checkConfigFile(self,config):
              

        self.RCF = ReadConfigFiles()
        try:
            self.cfg = self.RCF.ReadConfigRespectCase(config)
        except IOException, e:
            raise FIXEException("Problem reading FixEngine config file " + str(e))
        if not self.cfg:
            raise FIXEException("Problem reading FixEngine config file " )
        self.checkConfig(self.cfg)
        
    def checkConfig(self,cfg):
        


        self.FP =  FixMessage()
        f56=""
        f49=""
        c =  crypt(FIXEngine.CRYPTPass, self.CEN)



        if (cfg.get("fixengine_mode") != None):

            if (cfg.get("fixengine_mode").lower() == "a"):

                self.FLAG_modeInitiator=False
                self.m_logger.info("listening for incoming connection")
            
        else:
            self.FLAG_modeInitiator=True
            
        if (self.FLAG_modeInitiator):

            if (cfg.get("fixengine_host") == None ):

                raise FIXEException("Parameter fixengine_Host missing from configuration file")
            else:
                self.FIXHost=cfg.get("fixengine_host")
                self.m_logger.info("host = "+self.FIXHost)
    
        
        if (cfg.get("fixengine_service") == None ):
            raise FIXEException("Parameter fixengine_Service missing from configuration file")
        
        else:
            self.FIXService= int(cfg.get("fixengine_service"))
            self.m_logger.info("service = "+str(self.FIXService))
        

        if cfg.get("fixengine_seqnumfile") == None :
            raise FIXEException("Parameter fixengine_seqnumfile missing from configuration file")
        

        if (cfg.get("fixengine_fixversion") == None ) :
            self.FIX_Head = "8=FIX.4.2"+ FixMessage.c_FixSep +"9="
        
        else:
            self.FIX_Head = "8="+cfg.get("fixengine_fixversion")+FixMessage.c_FixSep+"9="
            self.m_logger.info("FIX Version -ie FIXHead used is "+self.FIX_Head.replace(FIXTools.c_FixSep,'|'))
        
        if (cfg.get("fixengine_heartbeat") == None ) :
            self.FP.f108_HeartBtInt="30"
            self.m_logger.warn("Parameter HeartBeat missing from configuration file, default 30")
        
        else:
            self.m_logger.info("heartbeat = "+cfg.get("fixengine_heartbeat"))
            self.FP.f108_HeartBtInt=cfg.get("fixengine_heartbeat")
        
        if (cfg.get("fixengine_sendtestrequest") != None ) :
            if (cfg.get("fixengine_sendtestrequest").lower() == "n"):
                self.FLAG_sendTimeout=False
                self.m_logger.info("Test Requests will not be sent ")
            
        
        if (cfg.get("fixengine_usedb") == None ) :
            self.m_logger.warn("Parameter fixengine_UseDB missing from configuration file, default n")
        
        else:
            if (cfg.get("fixengine_usedb").lower() == "y"):
                self.m_logger.info("FIX Messages will be stored in database")
                if (cfg.get("fixengine_dbconffile") == None ) :
                    raise FIXEException("Parameter fixengine_DBConfFile missing from configuration file")
                
                else:
                    if (cfg.get("fixengine_dbtableout") == None ) :
                        raise FIXEException("Parameter fixengine_DBTableOut missing from configuration file")
                    
                    else:
                        self.TableSent = cfg.get("fixengine_dbtableout")
                    
                    if (cfg.get("fixengine_dbtablein") == None ) :
                        raise FIXEException("Parameter fixengine_DBTableIn missing from configuration file")            
                    else:
                        self.TableRead = cfg.get("fixengine_dbtablein")
                    
                    self.DBT =  dbtools(cfg.get("fixengine_dbconffile"))
                    if (cfg.get("fixengine_processresend").lower() == "y"):
                        self.FLAG_ProcessResend=True
                        self.m_logger.info("FIX Engine will resend FIX messages on resend request")
                        self.FLAG_ProcessResend = True
                    
                
            
        
        if (cfg.get("fixengine_checkseqnumreceived") == None ) :
            self.m_logger.warn("Parameter fixengine_CheckSeqNumReceived missing from configuration file, default n")
        
        else:
            if (cfg.get("fixengine_checkseqnumreceived").lower() == "y"):
                self.FLAG_CheckSeqnumReceived = True
                self.m_logger.info("FIX Engine will check the sequence number it receives")
            
            else:
                self.FLAG_CheckSeqnumReceived = False
                self.m_logger.info("FIX Engine will NOT check the sequence number it receives")
            
        

        if (cfg.get("fixengine_encryptedcompids")!=None):
            tmp = cfg.get("fixengine_encryptedcompids")
            if tmp.lower() == "n":
                self.encryptedCompIDs = False
        

        if (cfg.get("fixengine_usecompression")!=None):
            tmp = cfg.get("fixengine_usecompression")
            if (tmp.lower() == "y"):
                self.FLAG_useCompression = True
                self.m_logger.info("FIX Message compression in ON!")
            
        

        if (cfg.get("fixengine_testrequesttimeout")!=None):
            tmp = cfg.get("fixengine_testrequesttimeout")
            self.testrequesttimeout= int(tmp)
        
        self.m_logger.info("testrequesttimeout is set to "+str(self.testrequesttimeout))

        if (cfg.get("fixengine_heartbeatextdelta")!=None):
            tmp = cfg.get("fixengine_heartbeatextdelta")
            self.HeartBeatExtDelta= int(tmp)
        
        self.m_logger.info("HeartBeatExtDelta is set to "+str(self.HeartBeatExtDelta))

        if (cfg.get("fixengine_sendercompid") == None ) :
            raise FIXEException("Parameter fixengine_sendercompid missing from configuration file")
        
        else:
            f49=cfg.get("fixengine_sendercompid")
            if (self.encryptedCompIDs):
                try:
                    self.FP.f49_SenderCompID=c.checkCrypt(f49)
                except CryptException, e:
                    raise FIXEException("Crypt issue, "+str(e))
                
            
            else:
                self.FP.f49_SenderCompID=f49

        
        if (cfg.get("fixengine_targetcompid") == None ) :
            raise FIXEException("fixengine_targetcompid parameter missing from configuration file")
        
        else:
            f56=cfg.get("fixengine_targetcompid")
            if (self.encryptedCompIDs):
                try:
                    self.FP.f56_TargetCompID=c.checkCrypt(f56)
                except CryptException, e:
                    raise FIXEException("Crypt issue, "+str(e))
                
            
            else:
                self.FP.f56_TargetCompID=f56
        
        if (f49.find("clear:")>=0) or (f56.find("clear:")>=0):
            raise FIXEException("Problem reading FixEngine config file f49.indexOf(clear:)>=0")
        
    
        self.fixtools = FIXTools()



        if (cfg.get("fixengine_relyontestrequestforendofreset")!=None):
            if cfg.get("fixengine_relyontestrequestforendofreset").lower() == "n":
                self.FLAG_relyOnTestRequestForEndOfReset=False
            
        
        if (self.FLAG_relyOnTestRequestForEndOfReset):
            self.m_logger.info("Engine will rely on the other side sending a testrequest to detect end of resend")
        else:
            self.m_logger.info("Engine will NOT rely on the other side sending a testrequest to detect end of resend")


        if (cfg.get("fixengine_seqnumfile")==None):
            raise FIXEException("fixengine_seqnumfile parameter is missing")
        
        self.SeqNumFileOut =  SequenceNumberFile( TYPE.NUMBER_OUT, self.EN, cfg.get("fixengine_seqnumfile")+"Out.dat")
        self.SeqNumFileIn =  SequenceNumberFile( TYPE.NUMBER_IN, self.EN, cfg.get("fixengine_seqnumfile")+"In.dat")
        
        
    def  setMainFixParameters(self,fp) :
        c =  crypt(FIXEngine.CRYPTPass, self.CEN)
        self.FP =  FixMessage()
        try :
            self.FP.f49_SenderCompID = c.checkCrypt(fp.f49_SenderCompID)
        except CryptException,e :
            raise  FIXEException ("setting  FIX parameters failed due to : "+str(e))
        
        try:
            self.FP.f56_TargetCompID = c.checkCrypt(fp.f56_TargetCompID)
        except CryptException,e :
            raise  FIXEException ("setting  FIX parameters failed due to : "+str(e))
        
        self.FP.f95_RawDataLength = fp.f95_RawDataLength 
        self.FP.f96_RawData = fp.f96_RawData 
        self.FP.f98_EncryptMethod = fp.f98_EncryptMethod 
        self.FP.f108_HeartBtInt = fp.f108_HeartBtInt
    
    def  setFIXConnectionParams(self, host, service, senderCompID, targetCompID, heartbeat):
        if (self.FLAG_isLoggedIn):
            raise  FIXEException ("Server is logged in, can not set  parameters")
        
        if (self.m_socketConnector.isConnectionOpen()): 
            raise  FIXEException ("Socket is not closed, can not set  parameters")
        

        if (len(host)>0):
            self.FIXHost=host
        if (service>0):
            self.FIXService=service
        if (len(senderCompID)>0):
            self.FP.f49_SenderCompID=senderCompID
        if (len(targetCompID)>0):
            self.FP.f56_TargetCompID=targetCompID
        if (len(heartbeat)>0):
            self.FP.f108_HeartBtInt=heartbeat
            
    def __init__(self,*args):
        self.lock = Lock()
        self.m_logger = Logger.getLogger("WCFIXEngine")
        self.customHeaderTags=""
        self.timeOut = None
        self.DBT = None
        self.HB = None
        self.FP = None
        self.FIXHost = ""
        self.FIXService = None
        self.fixtools = None
        self.SeqNumFileOut = None
        self.SeqNumFileIn = None
        self.LS = None
        self.CEN = None
        self.FIX_Head = "8=FIX.4.2"+ FixMessage.c_FixSep +"9="
        self.FLAG_StopListen = False
        self.FLAG_StopSend = False
        self.FLAG_isLoggedIn = False
        self.FLAG_isStopping = False
        self.encryptedCompIDs = True
        self.FLAG_isInResend=False
        self.SequenceNumberInDuringResend =0
        self.storedFIXWhileResend = ""
        self.TableRead = ""
        self.TableSent=""

        self.FLAG_ProcessResend = False
        self.FLAG_CheckSeqnumReceived = False
        self.FLAG_checkUserPassword = False
        
        self.FLAG_modeInitiator = True
        self.FLAG_useCompression=False
        self.testrequesttimeout=10
        self.FLAG_sendTimeout=True
        self.HeartBeatExtDelta=10
        self.FLAG_relyOnTestRequestForEndOfReset=True
  
        
    
        if isinstance(args[0],FIXEventsNotifier):
            if len(args)==9:
                en=args[0]
                host=args[1] 
                service=args[2]
                heartbeat=args[3]
                SenderCompID=args[4]
                TargetCompID=args[5]
                sequenceNberFile=args[6]
                initiator=args[7]
                checkuserpassword=args[8]
                self.EN = en
                self.CEN =  CryptEventsNotifier(self)
                self.FLAG_modeInitiator = initiator
                self.FIXHost=host
                self.FIXService=service
                self.FIX_Head="8=FIX.4.2"+ FixMessage.c_FixSep +"9="
                self.FLAG_CheckSeqnumReceived=True
                self.FP =  FixMessage()
                self.FP.f108_HeartBtInt=heartbeat
                self.FP.f49_SenderCompID=SenderCompID
                self.FP.f56_TargetCompID=TargetCompID
                self.SeqNumFileOut =  SequenceNumberFile( TYPE.NUMBER_OUT, self.EN, sequenceNberFile+"Out.dat")
                self.SeqNumFileIn =  SequenceNumberFile( TYPE.NUMBER_IN, self.EN, sequenceNberFile+"In.dat")
                self.FLAG_checkUserPassword=checkuserpassword
                self.m_socketConnector =  SocketConnector(self.EN)
                self.FIXEngineEndConstructor()

        elif len(args)==2:
            
            if isinstance(args[1],FIXEventsNotifier):

                en=args[1]
                configFile =args[0]
                self.EN = en
                self.CEN = CryptEventsNotifier(self)

                self.checkConfigFile(configFile)
                self.m_socketConnector = SocketConnector(en)
                self.FIXEngineEndConstructor()

            if isinstance(args[0],FIXEventsNotifier):
                en=args[0]
                cfg=args[1]
                self.EN = en
                self.CEN = CryptEventsNotifier(self)
                self.checkConfig(cfg)
                self.m_socketConnector = SocketConnector(en)
                self.FIXEngineEndConstructor()
                
        elif len(args)==0:
            pass
        
        else:
            raise FIXEException("Bad arguments for constructor of FIXEngine!")
        
    def FIXEngineEndConstructor(self):
        self.fixtools = FIXTools()
        self.timeOut = TimeOut(self, self.m_logger)
        self.m_logger.info("FIX Engine Version 7.3")
  
  
    def getSequenceNumberOut(self):
        return self.SeqNumFileOut.getSequentialNumber()
    def getSequenceNumberIn(self):
        return self.SeqNumFileIn.getSequentialNumber()
    def getLoggedInStatus(self):
        return self.FLAG_isLoggedIn
    
    
    def Start(self,seqnumOut, seqnumIn, resetFlag, Login="", Password=""):
        self.FLAG_isStopping=False
        OK=True
        self.FLAG_StopSend = False
        self.FLAG_StopListen = False
        self.FLAG_isStopping = False

        if (seqnumOut > -1):
            self.SeqNumFileOut.setSequentialNumber(seqnumOut)
        if (seqnumIn > -1):
            self.SeqNumFileIn.setSequentialNumber(seqnumIn)

        self.m_logger.info("Starting FIXEngine with SeqNum OUT = " + str(self.SeqNumFileOut.getSequentialNumber()))
        self.m_logger.info("Starting FIXEngine with SeqNum IN = " + str(self.SeqNumFileIn.getSequentialNumber()))

        if (self.FLAG_modeInitiator):
            self.m_socketConnector.openConnection(self.FIXHost, self.FIXService)
            return self.Connect_LogonLoginPassword_HeartBeat(resetFlag,Login,Password)
        elif (self.FIXService>0):
            self.beginListenSocket( int(self.FIXService))
        else:
            raise FIXEException("Listening port invalid")
        return OK
     
    def StartWithExistingSocket(self,seqnumOut, seqnumIn, resetFlag, soc, Login="", Password=""):
        self.FLAG_isStopping=False
        self.FLAG_StopSend = False
        self.FLAG_StopListen = False
        self.FLAG_isStopping = False

        if (seqnumOut > -1):
            self.SeqNumFileOut.setSequentialNumber(seqnumOut)

        if (seqnumIn > -1):
            self.SeqNumFileIn.setSequentialNumber(seqnumIn)

        self.m_logger.info("Starting FIXEngine with SeqNum OUT = "+str(self.SeqNumFileOut.getSequentialNumber()))
        self.m_logger.info("Starting FIXEngine with SeqNum IN = "+str(self.SeqNumFileIn.getSequentialNumber()))

        if (soc!=None):
            if (self.FLAG_modeInitiator):
                self.m_logger.info("Starting FIXEngine in initiator mode with existing socket, check UserPassword is "+self.FLAG_checkUserPassword)
                return self.Connect_LogonLoginPassword_HeartBeat(resetFlag,Login,Password)
            else:
                self.m_logger.info("Starting FIXEngine in acceptor mode with existing socket, check UserPassword is "+self.FLAG_checkUserPassword)
                self.m_socketConnector.setSocket(soc)
                Thread(self).start()

                return True
        else:
            raise FIXEException ("FE Socket is None!")
        
    def beginListenSocket(self,service):
        self.LS =  ListenSocket(service, self, self.m_logger)
        self.LS.Start() #throws FIXTexception if fails
        Thread(self).start()

    def stopListenIncomingConnections(self):
        if (self.LS != None):
            
            try:
                self.LS.Stop()
            except FIXEException, e:
                self.m_logger.warn("Exception while stopping the listen stocket "+str(e))

    def closeSocket(self):
        self.FLAG_StopListen = True
        self.FLAG_StopSend = True
        self.m_socketConnector.closeConnection()

        wait=0
        while ((self.FLAG_isLoggedIn)and(wait<25)):
            wait+=1
            try:
                Thread.sleep(100)
            except Exception:
                pass #// sleep to get logout ack

        if (self.FLAG_isLoggedIn):
            self.FLAG_isLoggedIn=False
            self.m_logger.info("logged out status has been forced -ie client did not answer")
            
            
    def Connect_LogonLoginPassword_HeartBeat(self,resetFlag, Login, Password):
        self.Login(self.FP, resetFlag, Login, Password)
        wait=0
        while ((not self.FLAG_isLoggedIn)and(wait<50)):
            wait+=1
            try:
                Thread.sleep(100)
            except InterruptedException:
                pass

        if(self.FLAG_isLoggedIn):
            self.HB =  HeartBeat(self,self.FP)
            self.HB.Start()
            return True
        else:
            return False
    def Login(self,FP, resetFlag, Login, Password):
        if (self.FLAG_modeInitiator): # otherwise, we are already listening...
            Thread(self).start()
        Fix =  FixMessage()
        Fix.f108_HeartBtInt = FP.f108_HeartBtInt
        Fix.f35_MsgType = "A"
        Fix.f49_SenderCompID=FP.f49_SenderCompID
        Fix.f56_TargetCompID=FP.f56_TargetCompID
        Fix.f95_RawDataLength = self.FP.f95_RawDataLength
        Fix.f96_RawData = self.FP.f96_RawData
        Fix.f553_UserName = Login
        Fix.f554_Password = Password
        if (len(self.FP.f98_EncryptMethod)>0):
            Fix.f98_EncryptMethod = self.FP.f98_EncryptMethod
        else:
            Fix.f98_EncryptMethod = "0"

        if (resetFlag):
            self.m_logger.info("connecting with reset asked")
            Fix.f141_ResetSeqNumFlag = "Y"
        if(not self.sendFixMessToServer(Fix,0)):
            self.m_logger.error("issue sending login FixMessage")

    def StopHBLogout(self,reason):
        if (self.HB != None):
            self.HB.Stop()
        Fix =  FixMessage()
        Fix.f35_MsgType = "5"
        Fix.f49_SenderCompID=self.FP.f49_SenderCompID
        Fix.f56_TargetCompID=self.FP.f56_TargetCompID
        Fix.f58_Text=reason
        self.sendFixMessToServer(Fix,0)
 

    def Stop(self,reason="",issue=0):
        if (self.FLAG_isStopping):
            self.m_logger.info("stop requested while already stopping...,"+reason)
            return
        
        self.m_logger.info("Stopping Fix Engine, "+reason)
        self.FLAG_isStopping=True
        self.StopHBLogout(reason)
        self.stopListenIncomingConnections()
        self.FLAG_isInResend =False 

        wait=0
        while ((self.FLAG_isLoggedIn)and(wait<25)):
            wait+=1
            try:
                Thread.sleep(100)
            except Exception:
                pass
        self.closeSocket()

        if (self.FLAG_isLoggedIn): 
            self.FLAG_isLoggedIn=False
            self.m_logger.info("logged out status has been forced -ie client did not answer")
        
        self.EN.notifyLoggedOUT(reason,0)

    def resetSeqNumbers(self):
        if (self.FLAG_isLoggedIn):
            return False
        else:
            self.SeqNumFileIn.setSequentialNumber(1)
            self.SeqNumFileOut.setSequentialNumber(1)
            return True

    def getUTCTime(self,includems):
        if (includems):
            DateFormatUTCms = SimpleDateFormat("yyyyMMdd-HH:mm:ss.SSS")
            DateFormatUTCms.setTimeZone(TimeZone.getTimeZone("Universal"))
            return DateFormatUTCms.format(GregorianCalendar.getInstance().getTime())
        else:
            DateFormatUTC = SimpleDateFormat("yyyyMMdd-HH:mm:ss")
            DateFormatUTC.setTimeZone(TimeZone.getTimeZone("Universal"))
            return DateFormatUTC.format(GregorianCalendar.getInstance().getTime())
        
    def sendFixMessToServer (self, FixMessage, seqnum) :
        with self.lock:
            OK = True
            if (not self.FLAG_StopSend):
                if (seqnum > 0): 
                    self.SeqNumFileOut.setSequentialNumber(seqnum)
                elif (FixMessage.f43_PossDupFlag.lower() == 'y' ):
                    self.SeqNumFileOut.incrementSequentialNumber()
                if (len(FixMessage.f49_SenderCompID)==0):
                    FixMessage.f49_SenderCompID = self.FP.f49_SenderCompID
                if (len(FixMessage.f56_TargetCompID)==0):
                    FixMessage.f56_TargetCompID = self.FP.f56_TargetCompID
    
                FIX=""

                FIX="35=" + FixMessage.f35_MsgType + FixMessage.c_FixSep + "34=" + str(self.SeqNumFileOut.getSequentialNumber())+ FixMessage.c_FixSep
                if (len(self.customHeaderTags)>0):
                    FIX+=self.customHeaderTags.replace('|',FixMessage.c_FixSep)
                
                if (FIX.endswith(FixMessage.c_FixSep+"")):
                    FIX+="52="+self.getUTCTime(False)+ FixMessage.c_FixSep
                
                else:
                    FIX+=FixMessage.c_FixSep + "52="+self.getUTCTime(False)+ FixMessage.c_FixSep
                
    
                FIX+=FixMessage.buildMsg()
    
                FIX = self.FIX_Head + str(len(FIX))+ FixMessage.c_FixSep + FIX
                FIX += "10=" + self.getChecksum(FIX) + FixMessage.c_FixSep
                try:
                    OK = self.SendFixMessage(FIX) 
                
                except IOException, e:
                    self.m_logger.fatal("Exception in Write Server : "+str(e))
                    OK = False
                except FIXEException, e:
                    self.m_logger.fatal("Exception in Write Server : "+str(e))
                    OK = False
                if (OK) :
                    self.LogMessageFIXSend(FIX.replace(FixMessage.c_FixSep,'|'))
                    if (self.DBT != None):
                        if (len(self.fixtools.getField(FIX,"49"))>0): 
                            if (FixMessage.f43_PossDupFlag.lower() == 'y'): #dont store resent message (same seqnumber)
                                self.DBT.StoreForFix(self.TableSent, self.fixtools.getField(FIX,"34"),FIX.replace(FixMessage.c_FixSep,'|'))
                
                elif FixMessage.f43_PossDupFlag.lower() != "Y".lower():
                    self.SeqNumFileOut.decrementSequentialNumber()
                return OK
            else:
                return False
        

 
        def sendFixStringToServer (self, Fix, seqnum) :
            OK = True
            if (not self.FLAG_StopSend):
                if (seqnum > 0) :
                    self.SeqNumFileOut.setSequentialNumber(seqnum)
                Fix=self.fixtools.ChangeField(Fix,"49",self.FP.f49_SenderCompID)
                Fix=self.fixtools.ChangeField(Fix,"56",self.FP.f56_TargetCompID)
                if (self.fixtools.getField(Fix,"43").lower() == 'y'): # we need to use same sequence number during retrans, seqnum is already in Fix
                    self.SeqNumFileOut.incrementSequentialNumber()
                    Fix=self.fixtools.ChangeField(Fix,"34",str(self.SeqNumFileOut.getSequentialNumber()))
                Fix=self.fixtools.NewSizeNewCheckSum(Fix)
                try :
                    self.SendFixMessage(Fix)
                except IOException, e:
                    self.m_logger.error("Exception in Write Server : "+str(e))
                    OK = False
                except FIXEException, e:
                    self.m_logger.fatal("Exception in Write Server : "+str(e) )
                    OK = False
                if (OK) :
                    self.LogMessageFIXSend(Fix.replace(FIXTools.c_FixSep,'|'))
                    if (self.DBT != None):
                        if (len(self.fixtools.getField(Fix,"49"))>0):
                            if (len(self.fixtools.getField(Fix,"43"))==0): #// dont store resent message (same seqnumber)
                                self.DBT.StoreForFix(self.TableSent, self.fixtools.getField(Fix,"34"),Fix.replace(FIXTools.c_FixSep,'|'))
                elif not self.fixtools.getField(Fix,"43").lower() != "Y".lower():
                    self.SeqNumFileOut.decrementSequentialNumber()
                return OK
            else:
                return False
    def getChecksum(self,S_FIX):
        i_tmp=0
        for i in xrange(len(S_FIX)):
            i_tmp = i_tmp + ord(S_FIX[i])
        I_tmp = int(i_tmp%256)
        if (len(str(I_tmp))<2):
            return "00"+str(I_tmp)
        elif (len(str(I_tmp))<3):
            return "0"+str(I_tmp)
        else:
            return str(I_tmp)
        
        
        
        
    def Listen(self):
        s_FixTmp = ""
        b_IsLength=False
        length=0
        b_IsCheckSum = False
        b_FullyReceived = False
        i_tmp = 0
        read=0

        msg = None

        if ( not self.m_socketConnector.isConnectionOpen()):
            return ""

        while True:
            if ( not self.m_socketConnector.isConnectionOpen()):
                return ""
            i_tmp = self.m_socketConnector.readCharFromSocket()
            if (i_tmp == -1):
                if (not self.FLAG_isStopping):
                    self.m_logger.error("Socket closed? listen loop will stop FixEngine i_tmp =-1")
                    self.FLAG_isLoggedIn=False # socket closed -> client wont answer logout
                    self.Stop("stop requested by listen thread") #//does not always throw an exception...

            else:
                s_FixTmp = s_FixTmp + chr(i_tmp)
                if ((s_FixTmp).endswith(FIXTools.c_FixSep+"9=")):
                    b_IsLength = True
                if ((b_IsLength) and (chr(i_tmp) == FIXTools.c_FixSep)):
                    b_IsLength=False
                    print s_FixTmp
                    sLength = s_FixTmp[s_FixTmp.index(FIXTools.c_FixSep)+3:len(s_FixTmp)-1]
                    try:
                        length = int(sLength)
                    except NumberFormatException:
                        self.m_logger.error("Exception parsing length=" + s_FixTmp)
                        length = 0
                while ((length>0)and(read>=0)):
                    msg = jarray.zeros(length,'b')
                    read = self.m_socketConnector.readFromSocket(msg, 0, length)
                    if (read>0):
                        a = msg
                        s_FixTmp = s_FixTmp + a[0: read]
                        length -= read
                        b_IsLength = False

                if (s_FixTmp.endswith(FIXTools.c_FixSep+"10=")):
                    b_IsCheckSum = True
                if b_IsCheckSum and (chr(i_tmp) == FIXTools.c_FixSep):
                    b_FullyReceived = True
            if  b_FullyReceived and self.FLAG_StopListen:
                break

            if (self.FLAG_StopListen):
                s_FixTmp = ""
            if ((b_FullyReceived)and(self.FLAG_useCompression)):
                s_FixTmp=self.fixtools.unzip(s_FixTmp)
        return s_FixTmp
        
    def  SendFixMessage(self,s_FIX):
        if (self.FLAG_useCompression):
            try:
                s_FIX=self.fixtools.zip(self.FIX_Head, s_FIX)
            except IOException, e:
                raise FIXEException("Compress error, "+str(e))
            message = jString(s_FIX).getBytes("ISO-8859-1")    
            return True
        else:
            message = jString(s_FIX).getBytes()
        return self.m_socketConnector.writeToSocket(message)
    
    def checkSeqNumReceived(self,FIX):
        OK = True
        SeqNumReceived = int(self.fixtools.getField(FIX, "34"))
        MsgType = self.fixtools.getField(FIX,"35")
        if (self.FLAG_isInResend) :
            if (self.fixtools.getField(FIX, "43").lower() == "Y".lower()) :
                if (SeqNumReceived < (self.SequenceNumberInDuringResend + 1)) :
                    self.m_logger.warn(
                            "Received smaller Sequence Number than expected during resend "
                            + SeqNumReceived + " < "
                            + (self.SequenceNumberInDuringResend + 1))
                    OK = False

                    self.Stop("Received smaller Sequence Number than expected during resend")

                    self.m_logger.error("Received smaller Sequence Number than expected during resend")
                
                elif (SeqNumReceived > (self.SequenceNumberInDuringResend + 1)) :
                    self.m_logger.error("Received higher Sequence Number than expected during resend "
                            + SeqNumReceived + " > "
                            + (self.SequenceNumberInDuringResend + 1))
                    OK = False

                    self.Stop("Received higher Sequence Number than expected during resend")

                    self.m_logger.error("Received higher Sequence Number than expected during resend")
                
                else:
                    self.SequenceNumberInDuringResend+=1
            else:
                if (SeqNumReceived >= (self.SeqNumFileIn.getSequentialNumber() + 1)) : 
                    if ((MsgType.equals("1")) or (not self.FLAG_relyOnTestRequestForEndOfReset)): 
                        self.FLAG_isInResend = False
                        if (self.fixtools.getField(self.storedFIXWhileResend, "35") == "A") :
                            self.m_logger.info("processing stored FIX Message seqnum "
                                    + self.fixtools.getField(self.storedFIXWhileResend, "34") + " "
                                    + OK)
                            try:
                                self.ProcessFIX(self.storedFIXWhileResend)
                            
                            except FIXEException,e:
                                self.m_logger.error(str(e)
                                        + "\nFIX msg (while resend)\n"
                                        + self.storedFIXWhileResend)
                        else:
                            self.m_logger.info("Stored FIX message was login message - not processed again")

                        if (SeqNumReceived > self.SeqNumFileIn.getSequentialNumber() + 1):
                            self.m_logger.info("end resend sequence - but system sent another seqnum > expected, asking resend again, "+ str(self.SeqNumFileIn.getSequentialNumber()))
                            self.getInResendMode(FIX, SeqNumReceived)
                            OK=False
                        elif (SeqNumReceived ==self.SeqNumFileIn.getSequentialNumber() + 1):
                            self.m_logger.info("end reset/restart sequence - next time (should be now=testrequest), I will expect : "
                                    +  str(self.SeqNumFileIn.getSequentialNumber() + 1))
                            self.m_logger.info("Processing last FIX message received that triggered end of resend")
                            try:
                                self.ProcessFIX(FIX)
                            except FIXEException, e:
                                self.m_logger.error(str(e)+ "\nFIX msg (while resend)\n"+ FIX)
                            self.SeqNumFileIn.incrementSequentialNumber()
                            self.m_logger.info("Fully ended reset/restart sequence - next time, I will expect : "
                                    +  str(self.SeqNumFileIn.getSequentialNumber() + 1))
                        else:
                            self.m_logger.fatal("Something really wrong has happened")
                    else:
                        self.m_logger.info("Other side sent message while I asked for resendrequest - I will not process it "+SeqNumReceived)
                        OK=False
                elif (SeqNumReceived == (self.SequenceNumberInDuringResend + 1)) :
                    self.m_logger.info("while in resendmode, received msg, which seqnum matches expected regular seqnum. That puts end to resend procedure. Note, no possdup flag")
                    self.SeqNumFileIn.setSequentialNumber(self.SequenceNumberInDuringResend + 1)
                    self.FLAG_isInResend = False
                else:
                    self.m_logger.fatal("Received message without PossDup Flag at Y during resend")
                    OK = False
                    self.Stop("Received message without PossDup Flag at Y during resend")
                    self.m_logger.fatal("Received message without PossDup Flag at Y during resend")
         
        else : 
            if (self.fixtools.getField(FIX, "43") == "Y") :
                self.m_logger.fatal("Received PossDup while not in requested resend session (Stopping) ")
                OK = False
                self.Stop("Received PossDup while not in requested resend session (Stopping)")
            elif (SeqNumReceived < (self.SeqNumFileIn.getSequentialNumber() + 1)) :
                self.m_logger.fatal("received smaller sequence number than expected (Stopping) "
                        + self + "   " + SeqNumReceived + " < "
                        + (self.SeqNumFileIn.getSequentialNumber() + 1))
                OK = False

                self.Stop("Received smaller sequence number than expected (Stopping)")

            elif (SeqNumReceived > (self.SeqNumFileIn.getSequentialNumber() + 1)) :
                self.getInResendMode(FIX, SeqNumReceived)
                OK = False
            
            if (not self.FLAG_isInResend) :
                self.SeqNumFileIn.incrementSequentialNumber()
        return OK
    
    def getInResendMode(self,FIX, SeqNumReceived ):
        self.FLAG_isInResend = True
        self.storedFIXWhileResend = FIX
        self.SequenceNumberInDuringResend = self.SeqNumFileIn.getSequentialNumber()
        self.m_logger.warn("Received higher Sequence Number than expected "
                + SeqNumReceived + " > "
                + (self.SeqNumFileIn.getSequentialNumber() + 1))
        self.m_logger.info("Storing message, seqnum "+ self.fixtools.getField(FIX, "34"))
        self.sendResendRequest(SeqNumReceived)
        self.SeqNumFileIn.setSequentialNumber(SeqNumReceived)
        
    def ProcessFIX(self,s_FIX):
        if (self.DBT != None):
            if (len(self.fixtools.getField(s_FIX,"49"))>0):
                self.DBT.StoreForFix(self.TableRead, self.fixtools.getField(s_FIX,"34"),s_FIX.replace(FIXTools.c_FixSep,'|'))

        MsgType = self.fixtools.getField(s_FIX,"35")

        if (MsgType == "A"):
            if (self.FLAG_checkUserPassword):
                if (len(self.fixtools.getField(s_FIX,"553"))>0)and(len(self.fixtools.getField(s_FIX,"554"))>0):
                    if (not (self.EN.checkUserPassword(self.fixtools.getField(s_FIX,"553"),self.fixtools.getField(s_FIX,"554")))):
                        self.Stop("User logon rejected")

                        raise FIXEException ("User logon rejected - dropping connection")
                else:
                    self.Stop("User information missing from logon message")

                    raise FIXEException ("User information missing from logon message")

            self.FLAG_isLoggedIn=True #// almost True - login answered or requested
            if (self.FLAG_sendTimeout):
                self.timeOut.Start(self.FP, int(self.fixtools.getField(s_FIX,"108")),self.testrequesttimeout, self.HeartBeatExtDelta)
            if (self.FLAG_CheckSeqnumReceived):
                self.checkSeqNumReceived(s_FIX) #// check seqnum after login !
            if (not self.FLAG_modeInitiator):
                try:
                    Thread.sleep(2000)
                except Exception:
                    pass #// ostream might not be ready !
                self.Connect_LogonLoginPassword_HeartBeat(False,"","")
                
        elif (MsgType == "2"): #// ResendRequest
            self.m_logger.warn("Resend Request Received")
            if (self.HB != None):
                self.HB.Stop()
            if (self.DBT != None):
                if (self.FLAG_ProcessResend):
                    self.ProcessResendRequest(s_FIX)
                else:
                    SendGapFill=True
            else:
                SendGapFill=True
            if(SendGapFill):
                self.m_logger.warn("Sending GapFill")
                Fix =  FixMessage()
                Fix.f35_MsgType = "4"
                Fix.f49_SenderCompID=self.FP.f49_SenderCompID
                Fix.f56_TargetCompID=self.FP.f56_TargetCompID
                Fix.f43_PossDupFlag = "Y"
                Fix.f123_GapFillFlag = "Y"
                old_seq = self.SeqNumFileOut.getSequentialNumber()
                self.SeqNumFileOut.setSequentialNumber( int(self.fixtools.getField(s_FIX,"7")))
                Fix.f36_NewSeqNum =  str(old_seq+1)
                self.sendFixMessToServer(Fix,0)
                self.SeqNumFileOut.setSequentialNumber(old_seq)
                try:
                    Thread.sleep(2000)
                except Exception:
                    pass
            
            if (self.HB != None):
                self.HB.Start()

        elif (MsgType == "1"): #// TestRequest -> send HB!
            self.m_logger.warn("Sending answer to TestRequest")
            Fix =  FixMessage()
            Fix.f35_MsgType = "0"
            Fix.f49_SenderCompID = self.FP.f49_SenderCompID
            Fix.f50_SenderSubID = "ADMIN"
            Fix.f57_TargetSubID = "ADMIN"
            Fix.f56_TargetCompID = self.FP.f56_TargetCompID
            Fix.f112_TestReqID = self.fixtools.getField(s_FIX,"112")
            self.sendFixMessToServer(Fix,-1)
        
        elif (MsgType == "4"): #// Reset Request
            self.m_logger.warn("Reset Request received")

            if(self.FLAG_isInResend):
                self.SequenceNumberInDuringResend =  int(self.fixtools.getField(s_FIX,"36"))-1
            else:
                self.SeqNumFileIn.setSequentialNumber( int(self.fixtools.getField(s_FIX,"36"))-1)
            
            if (len(self.storedFIXWhileResend)>0):
                if self.fixtools.getField(s_FIX, "36") == self.fixtools.getField(self.storedFIXWhileResend, "34"):
                    self.EN.notifyMsg("Server reset to stored FIX message, ",ErrorLevel.INFO)
                    self.m_logger.info("processing stored FIX Message seqnum "
                            + self.fixtools.getField(self.storedFIXWhileResend, "34") + " "
                            + " as per reset request")
                    try:
                        self.ProcessFIX(self.storedFIXWhileResend)
                    except FIXEException,e:
                        self.m_logger.error(str(e)
                                + "\nFIX msg (while reset)\n"
                                + self.storedFIXWhileResend)

        elif (MsgType == "5"): 
            if (self.FLAG_isStopping): 
                self.FLAG_isLoggedIn=False 
                self.m_logger.info("Logout accepted")
            
            else:
                self.m_logger.warn("logout requested by other side")
                self.FLAG_isLoggedIn=False
                self.Stop("logout requested by other side",0)
        elif (MsgType == "0"): 
            self.EN.processFIXMessage(s_FIX)

    def ProcessResendRequest(self, Fix):
        tmpVec = self.DBT.GetFix(self.TableSent, self.fixtools.getField(Fix,"7"), self.fixtools.getField(Fix,"16")) #should return list
        if (tmpVec !=None):
            for e in tmpVec:
                s_tmp = e.replace('|',FIXTools.c_FixSep)
                if (len(self.fixtools.getField(s_tmp,"43"))==0):
                    s_tmp = self.fixtools.AddField(s_tmp,"43","Y")
                    self.sendFixStringToServer(s_tmp,-1)

    def sendResendRequest(self,SeqNumReceived):
        Fix1 =  FixMessage()
        Fix1.f49_SenderCompID=self.FP.f49_SenderCompID
        Fix1.f56_TargetCompID=self.FP.f56_TargetCompID
        Fix1.f35_MsgType = "2"
        Fix1.f50_SenderSubID = "ADMIN"
        Fix1.f57_TargetSubID = "ADMIN"
        Fix1.f7_BeginSeqNum =  str(self.SeqNumFileIn.getSequentialNumber() + 1)
        Fix1.f16_EndSeqNo =  str(SeqNumReceived-1)
        self.sendFixMessToServer(Fix1,-1)

    def checkFIXChecksum(self,Fix):
        CheckSum = self.fixtools.getField(Fix,"10")
        if (len(CheckSum)==3):
            if (CheckSum == self.fixtools.getField(self.fixtools.NewChecksum(Fix),"10")):
                return True
            else:
                return False
        else:
            return False
    def CRYPT_NotifyMsg(self,Msg,level):
        if (level == ErrorLevel.FATAL):
            self.m_logger.fatal(Msg)
        elif (level== ErrorLevel.WARNING):
            self.m_logger.warn(Msg)
        elif (level== ErrorLevel.INFO):
            self.m_logger.info(Msg)
        elif (level == ErrorLevel.DEBUG):
            self.m_logger.debug(Msg)
    def LogMessageFIXRecv(self,Msg):
        self.EN.notifyFIXRecvLog(Msg)
    
    def LogMessageFIXSend(self,Msg):
        self.EN.notifyFIXSendLog(Msg)

    def stopListeningThread_CrashEngine(self):
        self.FLAG_StopListen=True

    def setFIXVersion (self,v):
        if (not self.FLAG_isLoggedIn):
            self.FIX_Head = "8="+v+FixMessage.c_FixSep+"9="
            self.m_logger.info("FIXHead used is "+self.FIX_Head.replace(FIXTools.c_FixSep,'|'))
            return True
        else:
            return False
    def setCustomHeaderTags(self, tags):
        self.customHeaderTags=tags       
        
    def setSocket(self, s):
        self.m_socketConnector.setSocket(s)
        
    def run(self):
        s_FIX="";
        keepgoing=True;
        while True:
            if ( not self.m_socketConnector.isConnectionOpen()):
                try:
                    Thread.sleep(100);
                except InterruptedException:
                    break
                continue
            try:
                s_FIX = self.Listen()
            except IOException, e:
                keepgoing=False
                self.m_logger.warn("IOException while listening : "+str(e))
                if (( not self.FLAG_StopListen) and (not self.FLAG_isStopping)): #// otherwise, stop twice... isStopping added in 3.7.1
                    self.Stop("within run, Listen threw IOException")
                
                s_FIX = "" #// had issues with FIX message processed twice
            
            except FIXEException, e:
                keepgoing=False

                self.m_logger.warn("FIXEException while listening : "+str(e))
                if( not self.FLAG_StopListen): #// otherwise, stop twice...
                    self.Stop("within run, Listen threw FIXEException")
                
                s_FIX = "" #// had issues with FIX message processed twice
            
            if (keepgoing):
                if (not self.FLAG_StopListen):
                    self.LogMessageFIXRecv(s_FIX.replace(FixMessage.c_FixSep,'|'))
                    self.timeOut.ResetTimeOut();
                    if (self.checkFIXChecksum(s_FIX)):
                        if (self.FLAG_CheckSeqnumReceived) and not (self.fixtools.getField(s_FIX,"35").lower() == "A".lower()):
                            #// forces process message even if bad seqnum
                            if (self.checkSeqNumReceived(s_FIX)):
                                try:
                                    self.ProcessFIX(s_FIX)
                                except FIXEException, e:
                                    self.m_logger.error("Process FIX exception "+str(e)+"\nFIX msg\n"+s_FIX)
                        else:
                            try:
                                self.ProcessFIX(s_FIX)
                            except FIXEException, e:
                                self.m_logger.error("FIX msg exception " + s_FIX + ", Exception " + str(e))
                    else:
                        self.m_logger.error("Fix Message not valid "+s_FIX)
            else:
                try:
                    Thread.sleep(1)
                except Exception:
                    pass
            if not (not self.FLAG_StopListen) and (keepgoing):
                break 
