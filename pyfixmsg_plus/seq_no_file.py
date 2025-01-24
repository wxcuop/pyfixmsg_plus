import os

class FIXEException(Exception):
    pass

class SequenceNumberFile:
    def __init__(self, seq_type, fix_events_notifier, filename):
        self.m_EN = fix_events_notifier
        self.Path = filename
        self.m_SequentialNumber = 0
        self.read_from_file_the_sequential_number()

    def get_sequential_number(self):
        return self.m_SequentialNumber

    def set_sequential_number(self, seq_number):
        self.m_SequentialNumber = seq_number
        self.store_sequence_number(self.m_SequentialNumber)

    def increment_sequential_number(self):
        self.m_SequentialNumber += 1
        self.store_sequence_number(self.m_SequentialNumber)

    def decrement_sequential_number(self):
        self.m_SequentialNumber -= 1
        self.store_sequence_number(self.m_SequentialNumber)

    def store_sequence_number(self, seq_number):
        try:
            with open(self.Path, 'w') as file_out:
                file_out.write(str(seq_number))
        except (FileNotFoundError, IOError) as e:
            self.m_EN.FE_NotifyMsg(f"FAILED to write to file={self.Path}", "ERROR")

    def read_from_file_the_sequential_number(self):
        if not os.path.exists(self.Path):
            self.m_SequentialNumber = 0
            return

        try:
            with open(self.Path, 'r') as file_in:
                s_tmp = file_in.readline().strip()
                self.m_SequentialNumber = int(s_tmp) if s_tmp else 1
        except (FileNotFoundError, IOError) as e:
            self.m_EN.FE_NotifyMsg(f"FAILED to read from file={self.Path}", "ERROR")
            self.m_SequentialNumber = 1
        except ValueError:
            self.m_SequentialNumber = 1
        finally:
            try:
                file_in.close()
            except IOError:
                self.m_EN.FE_NotifyMsg(f"FAILED to close 
