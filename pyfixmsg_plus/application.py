from abc import ABC, abstractmethod

class Application(ABC):
    @abstractmethod
    def onCreate(self, sessionID):
        pass

    @abstractmethod
    def onLogon(self, sessionID):
        pass

    @abstractmethod
    def onLogout(self, sessionID):
        pass

    @abstractmethod
    def toAdmin(self, message, sessionID):
        pass

    @abstractmethod
    def fromAdmin(self, message, sessionID):
        pass

    @abstractmethod
    def toApp(self, message, sessionID):
        pass

    @abstractmethod
    def fromApp(self, message, sessionID):
        pass

    @abstractmethod
    def onMessage(self, message, sessionID):
        """Processing application message here"""
        pass
