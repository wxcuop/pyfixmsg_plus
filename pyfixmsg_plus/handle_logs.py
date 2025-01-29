import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
from errors import ErrorLevel

# Configure the logging
logger = logging.getLogger('handle_logs')
logger.setLevel(logging.INFO)

# Create a file handler that logs messages to a file with daily rotation
handler = TimedRotatingFileHandler('application.log', when='midnight', interval=1)
handler.suffix = '%Y%m%d'  # Add date suffix to the rotated log files
handler.setLevel(logging.INFO)

# Create a formatter that includes timestamps
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

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
        self.include_timestamp = include_timestamp
        self.rotate_file = rotate_file
        self.event_notifier = event_notifier
        self.use_stdout = False
        self.header = ""
        self.offset_date = 0

        if event_notifier:
            self.event_notifier.HLF_NotifyMsg("HandleLogFiles Version 2.8", ErrorLevel.INFO)

    def set_header(self, header):
        self.header = header

    def write_text(self, text, append_newline=True):
        if self.include_timestamp:
            text = datetime.now().strftime("%Y%m%d %H:%M:%S.%f") + " ; " + text
        if append_newline:
            text += os.linesep
        logger.info(text)

    def stop(self):
        for handler in logger.handlers:
            handler.close()
            logger.removeHandler(handler)

    def delete_file(self, file_name):
        try:
            os.remove(file_name)
            return True
        except OSError:
            return False

    def log_message(self, message, level):
        if level == ErrorLevel.INFO:
            logger.info(message)
        elif level == ErrorLevel.WARNING:
            logger.warning(message)
        elif level == ErrorLevel.ERROR:
            logger.error(message)
        if self.use_stdout:
            print(f"{level} {message}")

    def set_use_stdout(self, value):
        self.use_stdout = value

    def set_formatter(self, formatter):
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter(formatter))

    def set_offset_date(self, days):
        self.offset_date = days
