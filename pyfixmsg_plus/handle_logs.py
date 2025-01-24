import os
from datetime import datetime, timedelta
from fixcommon.errors import ErrorLevel

class HandleLogFilesEvents:
    def HLF_NotifyMsg(self, s, level):
        raise NotImplementedError('Subclass responsibility')

class HandleLogFilesEventsNotifier:
    def __init__(self, event):
        self.ste = event

    def HLF_NotifyMsg(self, s, level):
        self.ste.HLF_NotifyMsg(s, level)

class HandleLogFiles:
    def __init__(self, log_file_name, include_timestamp=True, rotate_file=True, event_notifier=None):
        self.log_file_name_orig = log_file_name
        self.log_file_name = log_file_name
        self.include_timestamp = include_timestamp
        self.rotate_file = rotate_file
        self.event_notifier = event_notifier
        self.use_stdout = False
        self.header = ""
        self.offset_date = 0
        self.stream_out = None
        self.prev_date = None
        self.formatter_timestamp = "%Y%m%d %H:%M:%S.%f"
        self.formatter_file_date = "%Y%m%d"
        
        if event_notifier:
            self.event_notifier.HLF_NotifyMsg("HandleLogFiles Version 2.8", ErrorLevel.INFO)

    def set_header(self, header):
        self.header = header

    def write_text(self, text, append_newline=True):
        self._write(text, append_newline)

    def _write(self, text, append_newline):
        current_date = datetime.now().strftime("%Y%m%d")
        day_now = datetime.strptime(current_date, "%Y%m%d") + timedelta(days=self.offset_date)

        if not self.prev_date:
            self.prev_date = day_now - timedelta(days=1)

        new_file = False

        if self.rotate_file and day_now > self.prev_date:
            self.prev_date = day_now
            if self.stream_out:
                self.stream_out.close()
                self.stream_out = None
            if ',' in self.log_file_name_orig:
                self.log_file_name = f"{self.log_file_name_orig.rsplit('.', 1)[0]}_{day_now.strftime(self.formatter_file_date)}.{self.log_file_name_orig.rsplit('.', 1)[1]}"
            else:
                self.log_file_name += f"_{day_now.strftime(self.formatter_file_date)}"
            self.log_file = self.log_file_name

        if not os.path.exists(self.log_file_name):
            try:
                open(self.log_file_name, 'a').close()
                new_file = True
            except IOError as e:
                raise IOError(f"ERROR: Cannot create file, {str(e)}")

        if not self.stream_out:
            try:
                self.stream_out = open(self.log_file_name, 'a')
            except FileNotFoundError as e:
                self.event_notifier.HLF_NotifyMsg(f"File not found {str(e)}", ErrorLevel.ERROR)

        if self.stream_out:
            if new_file and self.header:
                text = self.header + os.linesep + text

            if self.include_timestamp:
                text = datetime.now().strftime(self.formatter_timestamp) + " ; " + text

            if append_newline:
                text += os.linesep

            self.stream_out.write(text)
            self.stream_out.flush()
        else:
            raise IOError("Streamout null for some reason")

    def stop(self):
        if self.stream_out:
            try:
                self.stream_out.close()
            except IOError:
                self.event_notifier.HLF_NotifyMsg("Could not close the stream", ErrorLevel.WARNING)
        self.log_file = None

    def delete_file(self, file_name):
        try:
            os.remove(file_name)
            return True
        except OSError:
            return False

    def log_message(self, message, level):
        try:
            self.write_text(f"{level} {message}")
        except IOError:
            pass
        if self.use_stdout:
            print(f"{level} {message}")

    def set_use_stdout(self, value):
        self.use_stdout = value

    def set_formatter(self, formatter):
        self.formatter_file_date = formatter

    def set_offset_date(self, days):
        self.offset_date = days
