from java.io import IOException,File,FileOutputStream,FileNotFoundException
from java.text import SimpleDateFormat,ParseException
from java.util import Calendar
from fixcommon.errors import ErrorLevel
from java.lang import String as jString
from java.lang import System

class HandleLogFilesEvents(object):

    def HLF_NotifyMsg(self,s, level):
        raise NotImplementedError('Subclass responsibility')

class HandleLogFilesEventsNotifier(object):
    def __init__(self,event):
        self.ste = event

    def HLF_NotifyMsg(self,s, level):
        self.ste.HLF_NotifyMsg(s,level)

class HandleLogFiles:
    LogFile = None;
    StreamOut = None;
    prevDate = None;
    logFileName = "";
    logFileNameOrig="";
    includeTimeStamp = True;
    rotateFile = True;
    formatterTimestamp = SimpleDateFormat("yyyyMMdd HH:mm:ss.S");
    use_stdout=False;
    header="";
    formatterFileDate= SimpleDateFormat("yyyyMMdd");
    offsetDate=0;
    EN = None;

    def __init__(self, LogFileName, includeTimeStamp=True, rotateFile=True, en=None):
        if en:
            self.EN = en
            self.EN.HLF_NotifyMsg("HandleLogFiles Version 2.8",ErrorLevel.INFO)
        self.includeTimeStamp = includeTimeStamp;
        self.rotateFile = rotateFile;
        self.logFileNameOrig=LogFileName;
        self.logFileName = LogFileName;
        self.LogFile=File(self.logFileName);
        
    def setHeader(self,header):
        self.header=header
        
    def WriteText(self,s_Text,extendofline=True):
        self.Write(s_Text,extendofline)
        
    def Write(self,Text,RetChar):
        if self.LogFile:
            formatDay = SimpleDateFormat("yyyyMMdd")
            parseDay = SimpleDateFormat("yyyyMMdd")
            try:
                DayNow = parseDay.parse(formatDay.format(Calendar.getInstance().getTime()))
            except ParseException, e:
                self.EN.HLF_NotifyMsg("parseDay ParseException in Write, "+str(e),ErrorLevel.ERROR)
                raise IOException("error parsing day")
            c = Calendar.getInstance()
            c.setTime(DayNow)
            c.add(Calendar.DATE,HandleLogFiles.offsetDate)
            DayNow = c.getTime()
            if not self.prevDate:
                    c.setTime(DayNow)
                    c.add(Calendar.DATE, -1)
                    self.prevDate = c.getTime()
                    
            newFile = False
            
            if self.rotateFile:
                if DayNow.after(self.prevDate):
                    self.prevDate = DayNow
                    if self.Streamout:
                        self.StreamOut.close()
                        self.StreamOut = None
                    if jString(self.logFileNameOrig).lastIndexOf(',') > 0:
                        self.logFileName = jString(self.logFileNameOrig).substring(0,jString(self.logFileNameOrig).lastIndexOf('.'))+"_"+self.formatterFileDate.format(DayNow)+jString(self.logFileNameOrig).substring(jString(self.logFileNameOrig).lastIndexOf('.'),jString(self.logFileNameOrig).length())
                    
                    else:
                        self.logFileName += "_"+self.formatterFileDate.format(DayNow)
                    self.LogFile = File(self.logFileName)

            if not self.LogFile.exists():
                try:
                    self.LogFile.createNewFile()
                except IOException, e:
                    raise IOException("ERROR: Cannot create file, "+str(e))
                newFile=True
                
            if not self.StreamOut: 
                try:
                    self.StreamOut = FileOutputStream(self.logFileName,True)
                except FileNotFoundException, e:
                    self.EN.HLF_NotifyMsg("File not found "+str(e), ErrorLevel.ERROR)
                    
            if self.StreamOut:
                if newFile and jString(self.header).length() > 0:
                    Text = self.header+System.getProperty("line.seperator")+Text
                    
                if self.includeTimeStamp:
                    self.StreamOut.write(self.formatterTimestamp.format(Calendar.getInstance().getTime().toString().getBytes()))
                    Text = " ; " + Text
                    
                if RetChar:
                    Text += System.getProperty("line.seperator")
                self.StreamOut(jString(Text).getBytes())
                self.StreamOut.flush()
            else:
                raise IOException("Streamout null for some reason")
            
        def Stop(self):
            if self.StreamOut:
                try:
                    self.StreamOut.close()
                except IOException, e:
                    self.EN.HLF_NotifyMsg("Could not close the stream",ErrorLevel.WARNING)

            self.LogFile = None
            
        def DeleteFile(self,s_FileName):
            b_ok=True
            self.LogFile = File(s_FileName)
            if self.LogFile.exists():
                b_ok = self.LogFile.delete()
            return b_ok
        
        def logMessage(self,msg,level):
            try:
                self.WriteText(level + " " + msg)
            except IOException, e:
                pass
            if self.use_stdout:
                System.out.println(level + " " + msg)
        def setUse_stdout(self,v):
            self.use_stdout=v
            
        def setFormatter(self,f):
            self.formatterFileDate = f
            
        def setoffsetDate(self,days):
            self.offsetDate = days
            
            
                    




                        
            
                
        
        
        
