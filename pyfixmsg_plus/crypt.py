import os
import hashlib
import base64
from hmac import compare_digest
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

class CryptException(Exception):
    def __init__(self, msg):
        super(CryptException, self).__init__(msg)

class CryptEvents(object):
    def CRYPT_NotifyMsg(self, msg, level):
        raise NotImplementedError('Subclass responsibility')
        
class CryptEventsNotifier(object):  
    def __init__(self, cevent):
        self.ste = cevent
        
    def CRYPT_NotifyMsg(self, msg, level):
        self.ste.CRYPT_NotifyMsg(msg, level)
        
class crypt(object):
    def __init__(self, cryptpass, en, log=None):
        self.cryptpass = cryptpass
        self.EN = en
        self.L = log
        self.ITERATIONS = 1000
        
    def LogMessage(self, Msg, level):
        if self.EN:
            self.EN.CRYPT_NotifyMsg(Msg, level)
        if self.L:
            if level == "DEBUG":
                self.L.debug(Msg)
            elif level == "ERROR":
                self.L.error(Msg)
            elif level == "FATAL":
                self.L.fatal(Msg)
            elif level == "INFO":
                self.L.info(Msg)
            elif level == "WARNING":
                self.L.warn(Msg)
                
    def checkCrypt(self, param):
        CRYPTPassword = self.cryptpass.encode('utf-8')
        Res = ""
        if param.startswith("clear:"):
            self.LogMessage(param + ", will be encrypted", "INFO")
            encryptedValue = self.encrypt(CRYPTPassword, param.split(':', 1)[1])
            Res = encryptedValue
            self.LogMessage("Encrypted value is:\n" + encryptedValue, "INFO")
        else:
            self.LogMessage("decrypting " + param, "INFO")
            Res = self.decrypt(CRYPTPassword, param)
        return Res

    def encrypt(self, password, plaintext):
        salt = get_random_bytes(16)
        key = hashlib.pbkdf2_hmac('sha256', password, salt, self.ITERATIONS, dklen=32)
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
        return base64.b64encode(salt + cipher.nonce + tag + ciphertext).decode('utf-8')

    def decrypt(self, password, text):
        data = base64.b64decode(text)
        salt, nonce, tag, ciphertext = data[:16], data[16:32], data[32:48], data[48:]
        key = hashlib.pbkdf2_hmac('sha256', password, salt, self.ITERATIONS, dklen=32)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        try:
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return plaintext.decode('utf-8')
        except ValueError as e:
            raise CryptException(f"Decryption failed: {e}")
