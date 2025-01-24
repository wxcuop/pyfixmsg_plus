import threading
import time

class HeartBeat(threading.Thread):
    def __init__(self, fe, fp):
        super().__init__()
        self.fe = fe
        self.fp = fp
        self.b_continue = False

    def start_heartbeat(self):
        if not self.b_continue:
            self.b_continue = True
            self.start()

    def stop_heartbeat(self):
        self.b_continue = False

    def send(self, f_fixmess):
        self.fe.send_fixmess_to_server(f_fixmess, 0)

    def run(self):
        f_fixmess = FIXMess()
        f_fixmess.f35_MsgType = "0"
        f_fixmess.f49_SenderCompID = self.fp.f49_SenderCompID
        f_fixmess.f50_SenderSubID = "ADMIN"
        f_fixmess.f57_TargetSubID = "ADMIN"
        f_fixmess.f56_TargetCompID = self.fp.f56_TargetCompID
        interval = int(self.fp.f108_HeartBtInt) * 1000
        while self.b_continue:
            time.sleep(interval / 1000.0)
            if self.b_continue:
                self.send(f_fixmess)

# Example usage:
# heartbeat = HeartBeat(fe, fp)
# heartbeat.start_heartbeat()
# To stop: heartbeat.stop_heartbeat()
