from java.lang import Runnable,Thread,Integer,NumberFormatException
from java.io import File,FileOutputStream,FileNotFoundException,FileReader,IOException
from fixmessage import FixMessage
from threading import Lock
from fixcommon.errors import ErrorLevel

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)
#http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python  

TYPE = enum('NUMBER_IN','NUMBER_OUT')

class HeartBeat(Runnable):
    b_continue = False
    
    
    def __init__(self, fixengine,fixmessage):
        self.FE = fixengine
        self.FP = fixmessage
        self.lock = Lock()
        
    def Start(self):
        with self.lock:
            if not self.b_continue:
                self.t_thread = Thread(self)
                self.b_continue = True
                self.t_thread.start()            
                
    def Stop(self):
        with self.lock:
            self.b_continue = False
            self.t_thread = None
            
    def Send(self,fixmessage):
        self.FE.sendFixMessToServer(fixmessage,0)
        
    def run(self):
        message = FixMessage()
        message.f35_MsgType="0"
        message.f49_SenderCompID = self.FP.f49_SenderCompID
        message.f50_SenderSubID = "ADMIN"
        message.f57_TargetSubID = "ADMIN"
        message.f56_TargetCompID = self.FP.f56_TargetCompID
        i = int(self.FP.f108_HeartBtInt)*1000
        while True:
            try:
                Thread.sleep(i)
            except:
                pass
            if self.b_continue:
                self.Send(message) #avoid hb sent when stop requested
        
            if not self.b_continue:
                break

class TimeOut(Runnable):
    def __init__(self,fixengine,logger):
        self.FE = fixengine
        self.m_logger=logger
        self.b_run = True
        self.timeout=0
        self.testreqtimeout=0
        self.hbextdelta=0
        self.hbint=0
    
    def Start(self,fixmessage,hbint, testreqtimeout,hbextdelta):
        self.b_run=True
        self.hbint = hbint
        self.FP = fixmessage
        self.testreqtimeout = testreqtimeout
        self.hbextdelta = hbextdelta
        Thread(self).start()
        
    def StopTimeOut(self):
        self.b_run=False
    
    def ResetTimeOut(self):
        self.timeout=0
        
    def run(self):
        self.timeout=0
        FixTestReq = FixMessage()
        FixTestReq.f35_MsgType="1"
        FixTestReq.f49_SenderCompID = self.FP.f49_SenderCompID
        FixTestReq.f50_SenderSubID = "ADMIN"
        FixTestReq.f57_TargetSubID = "ADMIN"
        FixTestReq.f56_TargetCompID = self.FP.f56_TargetCompID
        FixTestReq.f112_TestReqID = "HB timed out"
        while True:
            try:
                Thread.sleep(1000)
            except:
                pass
            self.timeout+=1
            if self.timeout > self.hbint+self.hbextdelta:
                if self.b_run and self.FE.getLoggedInStatus():
                    self.FE.sendFixMessToServer(FixTestReq,-1)
                    try:
                        Thread.sleep(self.testreqtimeout*1000) #sleep this.testrequesttimeout seconds to allow other side to answer
                    except:
                        pass
                    
            if not (self.b_run and self.FE.getLoggedInStatus):
                break
        
class SequenceNumberFile(object):
    
    def __init__(self,seqtype,fixeventsnotifier,filename):
        self.m_EN = fixeventsnotifier
        self.Path = filename
        self.m_SequentialNumber = 0
        
    def getSequentialNumber(self):
        return self.m_SequentialNumber
    def setSequentialNumber(self,SeqNumber):
        self.m_SequentialNumber = SeqNumber
        self.StoreSequenceNumber(self.m_SequentialNumber)
        
    def incrementSequentialNumber(self):
        self.m_SequentialNumber+=1
        self.StoreSequenceNumber(self.m_SequentialNumber)
        
    def decrementSequentialNumber(self):
        self.m_SequentialNumber-=1
        self.StoreSequenceNumber(self.m_SequentialNumber)
        
    def StoreSequenceNumber(self,SeqNumber):
        try:
            StreamOut = FileOutputStream(self.Path)
        except FileNotFoundException:
            self.m_EN.notifyMsg("FAILED to open file=" + self.Path, ErrorLevel.ERROR);
        return
        try:
            StreamOut.write(Integer(SeqNumber).toString().getBytes());
            StreamOut.flush();
        except IOException: 
            self.m_EN.notifyMsg("FAILED to write to file=" + self.Path, ErrorLevel.ERROR)
        try:
            StreamOut.close()
 
        except IOException:
            self.m_EN.notifyMsg("FAILED to close file=" + self.Path, ErrorLevel.ERROR)
        StreamOut = None
    
    def ReadFromFileTheSequentialNumber(self):
        f = File(self.Path)
        if not f.exists():
            self.m_SequentialNumber = 0;
            f = None
            return
        f = None
        try: 
            FileR = FileReader(self.Path)
        except FileNotFoundException:
            self.m_EN.notifyMsg("FAILED to read from file=" + self.Path, ErrorLevel.ERROR);  
            self.m_SequentialNumber = 1;
        return
        s_tmp = ""
        
        i_tmp=0
        while (i_tmp > -1) and (i_tmp !='\n'): 
            try: 
                i_tmp = FileR.read()
            except IOException:
                pass
            if (i_tmp > -1) and (i_tmp !='\n'):
                s_tmp += chr(i_tmp)
        try:
            FileR.close()
        except IOException:
            self.m_EN.notifyMsg("FAILED close after read from file=" + self.Path, ErrorLevel.ERROR)  
        
        FileR = None;
     
        try:
            self.m_SequentialNumber = Integer(s_tmp).intValue()
        except NumberFormatException:
            self.m_SequentialNumber=1
