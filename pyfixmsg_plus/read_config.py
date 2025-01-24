from handle_logfile import HandleLogFiles
from java.io import IOException,File,FileReader 
from java.lang import System,Exception




class ReadConfigFiles:
    def __init__(self,*args):

        self.HLF = None
        if len(args) == 0:

            self.Start()
        else:
            if isinstance(args[0],HandleLogFiles):
                self.HLF = args[0]
                self.Start()
    
            if isinstance(args[0],File):
                FileR = FileReader(args[0])
                return self.ReadConfig(FileR, False)
            
            if isinstance(args[0],str):
                FileR = FileReader(args[0])
                return self.ReadConfig(FileR, False)
        
    
    def ReadConfigRespectCase(self,filename):
        FileR = FileReader(filename)
        return self.ReadConfig(FileR, True)
        
    
    def ReadConfig(self,FileR,respectCase=False):
        i_tmp=0
        c_tmp=' '
        s_tmp = ""
        s_Field = ""
        
        if not isinstance(FileR,FileReader):
            FileR = FileReader(FileR)
        h_cfg = dict()

        while True:
            i_tmp = FileR.read()
            if ( i_tmp > -1):
                c_tmp = chr(i_tmp)
                if(c_tmp!='\n') :
                    s_tmp += c_tmp
                if(c_tmp=='\n') :
                    if s_tmp.strip().rfind('=') > -1:
                        if (respectCase):
                            s_Field = s_tmp[0:s_tmp.index('=')].strip()
                        else:
                            s_Field = s_tmp[0:s_tmp.index('=')].lower().strip()
                            
                        h_cfg[s_Field]=s_tmp[s_tmp.index('=')+1:].strip()
                    s_tmp = ""
                    s_Field = ""
            else:
                break
        return h_cfg
        
    def Start(self):
        if self.HLF:
            try:
                self.HLF.WriteText("INFO : ReadConfigFiles version 1.2")
            except IOException, e:
                System.err.println("Could not write info message in Log file...."+str(e))
            except Exception, e:
                System.err.println("Could not write info message in Log file...."+str(e))
                
                
