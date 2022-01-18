#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Support for running "sequences" which are scripts running experiments.
The main feature is to move them into their own thread, so that the console
can be used for other commands.
"""
from itertools import compress
import threading
import time
import sys
import traceback
from measurement import _logger as _measlogger

_logger = _measlogger.getChild('sequence')


def list_sequences():
    """Returns a list of running sequences"""
    threads = threading.enumerate()
    mask = [isinstance(thread, Sequence) for thread in threads]
    seqs = list(compress(threads, mask))
    return seqs


class SequenceStopError(RuntimeError):
    """Used to abort a running Sequence"""
    pass


class Sequence(threading.Thread):
    def __init__(self, target=None, name=None, args=(), kwargs={}):
        """
        Creates a sequence object. Does not start it, call start() for that

        target : the function to run as a sequence
        name : the name of the sequence
        args, kwargs : these are passed to the target when it is called
        """
        self._pause_requested = False
        self._is_paused = False
        self._resume_requested = False
        self._stop_requested = False
        self._skip_requested = False
        if name is None:
            name = "Sequence"
        super().__init__(target=target, name=name, args=args, kwargs=kwargs)

    def run(self):
        """Override Thread.run to add logging. Do not call directly, use start()"""
        try:
            super().run()
            _logger.info(f"Sequence '{self.name}' completed")
        except SequenceStopError:
            _logger.warning(f"Sequence '{self.name}' stopping early")
        except Exception:
            _logger.critical("Unhandled Exception, Sequence terminated", exc_info=True)

    def _check_pause(self):
        """Call from target code when convienient to pause etc. Used in waits"""
        if self._is_paused:
            if self._pause_requested:
                _logger.warning("Tried to pause Sequence, but it is already paused")
                self._pause_requested = False
            if self._resume_requested:
                _logger.info(f"Resuming Sequence '{self.name}'")
                self._is_paused = False
                self._resume_requested = False
            self.start_time = time.time()
        else:
            if self._pause_requested:
                _logger.info(f"Pausing Sequence '{self.name}'")
                self._is_paused = True
                self._pause_requested = False
            if self._resume_requested:
                _logger.warning("Tried to resume Sequence, but it is already running")
                self._resume_requested = False
        return self._is_paused

    def _check_stop(self):
        """Call from target code when convienient to stop early. Used in waits"""
        if self._stop_requested:
            raise SequenceStopError()

    def start(self, multi_seq=False):
        """Starts the sequence"""
        if len(list_sequences()) > 0 and not multi_seq:
            raise RuntimeError("Another Sequence is running. Stop it or pass multi-seq=True")
        _logger.info(f"Starting Sequence '{self.name}'")
        super().start()

    def pause(self):
        """Pause the sequence at the next opportunity. Blocks until then"""
        self._pause_requested = True
        while not self._is_paused:
            time.sleep(0.1)

    def resume(self):
        """Restart a paused sequence"""
        self._resume_requested = True

    def stop(self):
        """Stop the sequence at the next opportunity. Blocks unitil then"""
        self._stop_requested = True
        self.join()

    def skip_wait(self):
        """The current or next wait will end immediately. Use with care."""
        self._skip_requested = True

    def currently_executing(self):
        """Get a traceback of the line currently being executed"""
        if self.is_alive():
            frame = sys._current_frames().get(self.ident, None)
            traceback.print_stack(frame, file=sys.stdout)
        else:
            print("The sequence is not running")


# TODO it would be good to be able to peek into the namespace of the running
# code to see how it is doing.
