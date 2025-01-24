import threading
from fixmessage import FixMessage
from threading import Lock
from fixcommon.errors import ErrorLevel

def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)

TYPE = enum('NUMBER_IN', 'NUMBER_OUT')

class HeartBeat(threading.Thread):
    b_continue = False

    def __init__(self, fixengine, fixmessage):
        super().__init__()
        self.FE = fixengine
        self.FP = fixmessage
        self.lock = Lock()

    def start(self):
        with self.lock:
            if not self.b_continue:
                self.b_continue = True
                super().start()

    def stop(self):
        with self.lock:
            self.b_continue = False

    def send(self, fixmessage):
        self.FE.sendFixMessToServer(fixmessage, 0)

    def run(self):
        message = FixMessage()
        message.f35_MsgType = "0"
        message.f49_SenderCompID = self.FP.f49_SenderCompID
        message.f50_SenderSubID = "ADMIN"
        message.f57_TargetSubID = "ADMIN"
        message.f56_TargetCompID = self.FP.f56_TargetCompID
        interval = int(self.FP.f108_HeartBtInt) * 1000
        while True:
            try:
                threading.Event().wait(interval / 1000)
            except:
                pass
            if self.b_continue:
                self.send(message)
            if not self.b_continue:
                break

class TimeOut(threading.Thread):
    def __init__(self, fixengine, logger):
        super().__init__()
        self.FE = fixengine
        self.logger = logger
        self.b_run = True
        self.timeout = 0
        self.testreqtimeout = 0
        self.hbextdelta = 0
        self.hbint = 0

    def start(self, fixmessage, hbint, testreqtimeout, hbextdelta):
        self.b_run = True
        self.hbint = hbint
        self.FP = fixmessage
        self.testreqtimeout = testreqtimeout
        self.hbextdelta = hbextdelta
        super().start()

    def stop_timeout(self):
        self.b_run = False

    def reset_timeout(self):
        self.timeout = 0

    def run(self):
        self.timeout = 0
        FixTestReq = FixMessage()
        FixTestReq.f35_MsgType = "1"
        FixTestReq.f49_SenderCompID = self.FP.f49_SenderCompID
        FixTestReq.f50_SenderSubID = "ADMIN"
        FixTestReq.f57_TargetSubID = "ADMIN"
        FixTestReq.f56_TargetCompID = self.FP.f56_TargetCompID
        FixTestReq.f112_TestReqID = "HB timed out"
        while True:
            try:
                threading.Event().wait(1)
            except:
                pass
            self.timeout += 1
            if self.timeout > self.hbint + self.hbextdelta:
                if self.b_run and self.FE.getLoggedInStatus():
                    self.FE.sendFixMessToServer(FixTestReq, -1)
                    try:
                        threading.Event().wait(self.testreqtimeout)
                    except:
                        pass
            if not (self.b_run and self.FE.getLoggedInStatus()):
                break

class SequenceNumberFile:
    def __init__(self, seqtype, fixeventsnotifier, filename):
        self.notifier = fixeventsnotifier
        self.path = filename
        self.sequential_number = 0

    def get_sequential_number(self):
        return self.sequential_number

    def set_sequential_number(self, seq_number):
        self.sequential_number = seq_number
        self.store_sequence_number(self.sequential_number)

    def increment_sequential_number(self):
        self.sequential_number += 1
        self.store_sequence_number(self.sequential_number)

    def decrement_sequential_number(self):
        self.sequential_number -= 1
        self.store_sequence_number(self.sequential_number)

    def store_sequence_number(self, seq_number):
        try:
            with open(self.path, 'w') as file:
                file.write(str(seq_number))
        except IOError:
            self.notifier.notifyMsg(f"FAILED to write to file={self.path}", ErrorLevel.ERROR)

    def read_sequence_number_from_file(self):
        try:
            with open(self.path, 'r') as file:
                self.sequential_number = int(file.readline().strip())
        except (IOError, ValueError):
            self.notifier.notifyMsg(f"FAILED to read from file={self.path}", ErrorLevel.ERROR)
            self.sequential_number = 1
