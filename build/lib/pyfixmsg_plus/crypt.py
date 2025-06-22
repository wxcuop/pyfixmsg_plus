import os
import hashlib
import base64
from hmac import compare_digest
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes

class CryptException(Exception):
    pass

class CryptEvents:
    def CRYPT_NotifyMsg(self, msg, level):
        raise NotImplementedError('Subclass responsibility')

class CryptEventsNotifier:
    def __init__(self, cevent):
        self.ste = cevent

    def CRYPT_NotifyMsg(self, msg, level):
        self.ste.CRYPT_NotifyMsg(msg, level)

class Crypt:
    def __init__(self, crypt_pass, event_notifier=None, logger=None, iterations=1000):
        self.crypt_pass = crypt_pass
        self.event_notifier = event_notifier
        self.logger = logger
        self.iterations = iterations

    def log_message(self, msg, level):
        if self.event_notifier:
            self.event_notifier.CRYPT_NotifyMsg(msg, level)
        if self.logger:
            log_methods = {
                "DEBUG": self.logger.debug,
                "ERROR": self.logger.error,
                "FATAL": self.logger.fatal,
                "INFO": self.logger.info,
                "WARNING": self.logger.warn
            }
            log_methods.get(level, self.logger.info)(msg)

    def check_crypt(self, param):
        crypt_password = self.crypt_pass.encode('utf-8')
        if param.startswith("clear:"):
            self.log_message(f"{param}, will be encrypted", "INFO")
            encrypted_value = self.encrypt(crypt_password, param.split(':', 1)[1])
            self.log_message(f"Encrypted value is:\n{encrypted_value}", "INFO")
            return encrypted_value
        else:
            self.log_message(f"Decrypting {param}", "INFO")
            return self.decrypt(crypt_password, param)

    def encrypt(self, password, plaintext):
        salt = get_random_bytes(16)
        key = hashlib.pbkdf2_hmac('sha256', password, salt, self.iterations, dklen=32)
        cipher = AES.new(key, AES.MODE_GCM)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode('utf-8'))
        return base64.b64encode(salt + cipher.nonce + tag + ciphertext).decode('utf-8')

    def decrypt(self, password, text):
        data = base64.b64decode(text)
        salt, nonce, tag, ciphertext = data[:16], data[16:32], data[32:48], data[48:]
        key = hashlib.pbkdf2_hmac('sha256', password, salt, self.iterations, dklen=32)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        try:
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return plaintext.decode('utf-8')
        except ValueError as e:
            raise CryptException(f"Decryption failed: {e}")
