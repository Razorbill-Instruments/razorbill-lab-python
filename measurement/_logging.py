#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""Provides logging functionality for the measurement module."""


import logging
from logging import FileHandler, StreamHandler, _defaultFormatter
from logging.handlers import SocketHandler, QueueHandler, QueueListener
import sys
import os
import builtins
import time
import queue
import copy
import threading
from socket import gethostname

try:
    import colorama
    colorama.init()
except ModuleNotFoundError:
    pass

have_ipython = getattr(builtins, "__IPYTHON__", False)
if have_ipython:
    import IPython

_rootlogger = logging.getLogger('razorbill_lab')
_exception_logger = _rootlogger.getChild('exception')
_listener = None
_LOG_FMT = '%(asctime)s [%(levelname)s] %(threadName)s > %(message)s'
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class _ColourFormatter(logging.Formatter):
    """Logging Formatter with coloured message (and traceback if on IPython).

    Will probably work on Linux/mac. Requires colorama to work on Windows.
    """

    COLOURS = {
        logging.DEBUG: "\x1b[35m",      # 35 = magenta
        logging.INFO: "\x1b[32m",       # 32 = green
        logging.WARNING: "\x1b[33m",    # 33 = yellow (often orange)
        logging.ERROR: "\x1b[31;1m",    # 31;1 = bold red
        logging.CRITICAL: "\x1b[41;37;1m"  # 41;30;1 = bold white on red
    }

    def formatMessage(self, record):
        colour = self.COLOURS.get(record.levelno)
        resp = super().formatMessage(record)
        return colour + resp + "\x1b[0m"


class _IPYthonFormatter(_ColourFormatter):
    """Uses IPython to format the traceback."""

    def format(self, record):
        super().format(record)  # populate record.message, record.asctime, record.exc_text
        s = [super().formatMessage(record)]
        if record.exc_info:
            ip = IPython.get_ipython()
            if issubclass(record.exc_info[0], SyntaxError):
                stb = ip.SyntaxTB.structured_traceback(*record.exc_info)
            else:
                stb = ip.InteractiveTB.structured_traceback(*record.exc_info)
            s += '\n'
            s += stb
        return ''.join(s)


class _QueueHandlerExc(QueueHandler):
    """QueueHandler which keeps the log message and exception text separate."""

    def prepare(self, record):
        record = copy.copy(record)
        if self.formatter is None:
            f = _defaultFormatter
        else:
            f = self.formatter
        # Populate record.message, record.asctime and record.exc_text
        f.format(record)
        # Strip things which may not be pickleable. Stripping record.args makes
        # record.msg useless, so replace it with the formatted message.
        record.msg = record.message
        record.args = None
        record.exc_info = None
        return record


class ThreadWithExcLog(threading.Thread):
    """A thread that will use the logger to log errors instead of printing to stderr.

    Works when calling with a target, won't work if subclassing and overriding run()
    """

    def run(self):
        """Do the actual work of the thread.

        Much like superclass version, but with exception logging
        """
        try:
            if self._target:
                self._target(*self._args, **self._kwargs)
        except Exception:
            _exception_logger.critical("Unhandled Exception, Thread terminating", exc_info=True)
        finally:
            # Avoid a refcycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            # (copied from the superclass)
            del self._target, self._args, self._kwargs


def _setup_logging(log_path=None):
    """Configure logging. Logs to console, file, and socket."""
    if have_ipython:
        console_formatter = _IPYthonFormatter(_LOG_FMT, datefmt=_DATE_FMT)
    else:
        console_formatter = _ColourFormatter(_LOG_FMT, datefmt=_DATE_FMT)
    console_handler = StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    log_queue = queue.Queue()
    queue_handler = _QueueHandlerExc(log_queue)

    root_logger = logging.getLogger('razorbill_lab')
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = [console_handler, queue_handler]

    file_formatter = logging.Formatter(_LOG_FMT, datefmt=_DATE_FMT)
    filename = "measurement log {}.log".format(time.strftime("%Y-%m-%d %H-%M-%S"))
    if log_path is None:
        log_path = os.getcwd()
    if not os.path.exists(log_path):
        raise ValueError(f"log_path ({log_path}) does not exist")
    filename = os.path.join(log_path, filename)
    file_handler = FileHandler(filename)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    socket_handler = SocketHandler('127.0.0.1', 19996)  # Cutelog port

    _listener = QueueListener(log_queue, file_handler, socket_handler, respect_handler_level=True)
    _listener.start()
    _listener._thread.name = "Logger"
    _rootlogger.info(f"Log started at: '{filename}' on '{gethostname()}'")


def _excepthook(etype, value, traceback):
    """Exception handler sys.excepthook. Sends the exception to the logger."""
    _exception_logger.critical('Unhandled Exception', exc_info=(etype, value, traceback))


def _excepthook_ip(self, etype, value, tb, tb_offset=None):
    """Exception handler for ipython. Sends the exception to the logger."""
    _exception_logger.critical('Unhandled Exception', exc_info=(etype, value, tb))


def _setup_exception_logging():
    """Register a hook for uncaught exceptions in the main thread."""
    if have_ipython:
        IPython.get_ipython().set_custom_exc((Exception,), _excepthook_ip)
    else:
        sys.excepthook = _excepthook
