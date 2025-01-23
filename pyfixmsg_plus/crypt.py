from com.sun.crypto.provider import SunJCE
from javax.crypto.spec import PBEKeySpec
import javax.crypto
from java.util import Random
from java.security import Security,NoSuchAlgorithmException
from errors import ErrorLevel
import jarray
from java.lang import Exception as JException
from javax.crypto import Cipher
import java
from java.io import IOException
from java.lang import String as jString
from sun.misc import BASE64Decoder,BASE64Encoder


#http://sourceforge.net/p/jython/mailman/message/30764474/
        

class CryptException (JException):
    def __init__(self,msg):
        super(CryptException,self).__init__(msg)

class CryptEvents(object):
    def CRYPT_NotifyMsg(self, msg, level):
        raise NotImplementedError('Subclass responsibility')
    
    
class CryptEventsNotifier(object):  
    def __init__(self,cevent):
        self.ste=cevent
        
    def CRYPT_NotifyMsg(self,msg, level):
        self.ste.CRYPT_NotifyMsg(msg, level)
        
class crypt(object):
    def __init__(self,cryptpass,en,log=None):
        #log is log4j
        self.cryptpass=cryptpass
        self.EN = en
        self.L = log
        self.Start(cryptpass)
        self.ITERATIONS = 1000
        
    def Start(self,cryptpass):
        self.LogMessage("crypt version 2.3", ErrorLevel.INFO)
        sunjce = SunJCE()       
        Security.addProvider(sunjce)
        self.CRYPTPass = self.cryptpass

    def LogMessage(self,Msg, level):
        if self.EN:
            self.EN.CRYPT_NotifyMsg(Msg, level)
        if self.L:
            if (level==ErrorLevel.DEBUG):
                self.L.debug(Msg)
        
            elif (level==ErrorLevel.ERROR):
                self.L.error(Msg)
        
            elif (level==ErrorLevel.FATAL):
                self.L.fatal(Msg)
            elif (level==ErrorLevel.INFO):
                self.L.info(Msg)
            elif (level==ErrorLevel.WARNING):
                self.L.warn(Msg);
    def checkCrypt(self,param):

        CRYPTPassword = jarray.zeros(len(self.CRYPTPass), 'c')
        for i in xrange(len(self.CRYPTPass)):
            CRYPTPassword[i]=self.CRYPTPass[i]
        Res=""
        if param.startswith("clear:"):
            self.LogMessage(param+", will be encrypted", ErrorLevel.INFO)
            encryptedValue=""
            encryptedValue = self.encrypt(CRYPTPassword, param[param.index(':') + 1:len(param)])
            Res=encryptedValue
            self.LogMessage("Encrypted value is:\n"+encryptedValue, ErrorLevel.INFO)
        else:
            self.LogMessage("decrypting "+param, ErrorLevel.INFO)
            Res=self.decrypt(CRYPTPassword,param)
            
        return Res
 
    def encrypt(self,password, plaintext):  
        #Begin by creating a random salt of 64 bits (8 bytes)
        salt = jarray.zeros(8, 'b')
        random = Random()
        random.nextBytes(salt)
        keySpec = PBEKeySpec(password)
        key = None
        keyFactory = None
        cipher = None
        try:
            keyFactory=javax.crypto.SecretKeyFactory.getInstance("PBEWithMD5AndDES")
        except NoSuchAlgorithmException, e:
            raise CryptException("NoSuchAlgorithmException, "+e.getMessage())
        
        try:
            key = keyFactory.generateSecret(keySpec)
        except java.security.spec.InvalidKeySpecException, e:
            raise CryptException("NoSuchAlgorithmException, "+e.getMessage())
            
        paramSpec = javax.crypto.spec.PBEParameterSpec(salt, self.ITERATIONS)            
       
        try:
            cipher = javax.crypto.Cipher.getInstance("PBEWithMD5AndDES")
        except NoSuchAlgorithmException, e:
            raise CryptException("NoSuchAlgorithmException, "+e.getMessage())
                  
        except javax.crypto.NoSuchPaddingException, e:
            raise CryptException("NoSuchPaddingException, "+e.getMessage())
        
        
        try:
            cipher.init(Cipher.ENCRYPT_MODE, key, paramSpec)
        except java.security.InvalidKeyException, e:
            raise CryptException("InvalidKeyException, "+e.getMessage())
        except java.security.InvalidAlgorithmParameterException, e:
            raise CryptException("InvalidAlgorithmParameterException, "+e.getMessage())
        
        ciphertext = None
        try:
            ciphertext = cipher.doFinal(plaintext.getBytes())
        except javax.crypto.IllegalBlockSizeException, e:
            raise CryptException("IllegalBlockSizeException, "+e.getMessage())
        except javax.crypto.BadPaddingException, e:
            raise CryptException("BadPaddingException, "+e.getMessage())
        
        encoder = BASE64Encoder()
        saltString = encoder.encode(salt)
        ciphertextString = encoder.encode(ciphertext)
        return saltString+ciphertextString

    def decrypt(self,password, text):
        salt = text.substring(0,12)
        ciphertext = text.substring(12,text.length())
        decoder = BASE64Decoder()
        try:
            saltArray = decoder.decodeBuffer(salt)
        except IOException, e:
            raise CryptException ("IOException, "+e.getMessage())
        
        try:
            ciphertextArray = decoder.decodeBuffer(ciphertext)
        except IOException, e:
            raise CryptException ("IOException, "+e.getMessage())
        
        keySpec = PBEKeySpec(password)
        
        try:
            keyFactory = javax.crypto.SecretKeyFactory.getInstance("PBEWithMD5AndDES")
        except NoSuchAlgorithmException, e:
            raise CryptException("NoSuchAlgorithmException, "+e.getMessage())
        
        try:
            key=keyFactory.generateSecret(keySpec)
        except java.security.spec.InvalidKeySpecException, e:
            raise CryptException("InvalidKeySpecException, "+e.getMessage())
        
        paramSpec = javax.crypto.spec.PBEParameterSpec(saltArray, self.ITERATIONS)
        
        try:
            cipher=Cipher.getInstance("PBEWithMD5AndDES")
        except NoSuchAlgorithmException, e:
            raise CryptException("NoSuchAlgorithmException, "+e.getMessage())
        except javax.crypto.NoSuchPaddingException, e:
            raise CryptException("NoSuchPaddingException, "+e.getMessage())
        
        try:
            cipher.init(Cipher.DECRYPT_MODE, key, paramSpec)
        except java.security.InvalidKeyException,e:
            raise CryptException("InvalidKeyException, "+e.getMessage())
        except java.security.InvalidAlgorithmParameterException,e:
            raise CryptException("InvalidAlgorithmParameterException, "+e.getMessage())
            
        try:
            plaintextArray = cipher.doFinal(ciphertextArray)
        except javax.crypto.IllegalBlockSizeException, e:
            raise CryptException("IllegalBlockSizeException, "+e.getMessage())
        except javax.crypto.BadPaddingException, e:
            raise CryptException("BadPaddingException, "+e.getMessage())
        
        
        return jString(plaintextArray)
        
        
        
            
        
            
        
        
        
        
        
        
            
        
     
