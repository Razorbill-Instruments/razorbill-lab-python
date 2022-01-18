#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
This module contains classes for recording measurement `Quantities` into
csv files. `Recorder`s record lines on demand, and `AutoRecorder`s record
lines at a regular interval.
"""

import csv
import subprocess
import os
import time
import json
import numpy as np
from socket import gethostname
from . import _logger as _measlogger
from . import ThreadWithExcLog, kst_binary

_logger = _measlogger.getChild('recorders')
recorder_registry = {}

# TODO: the Recorder class is a bit messy, _set_up_file in particular could do with refactoring.


class Recorder():
    """Record several `Quantity`s and write them to a file.

    Opens a CSV file and writes column headers into it.  Each time
    `record_line` is called, it will get the value of each quanity and add them
    to the file as a new line.

    Construction
    ------------
    filename : string, required
        filename to write the data to. Path and extension optional.
    quantities : itterable, required
        the ``Quantity``s to record.  If there is only one, put it in a list
    append : boolean, optional
        If true, and the file already exists, and has the same columns, append.
        Otherwise, warn and overwrite/create new file as per next argument.
    overwrite : boolean, optional
        If true, and the file already exists, it will be overwritten. Otherwise
        add a numeric suffix to the file name.
    metadata : dict or None, optional
        A dict of key: value pairs which will be added to the metadata written
        into the first line of the file. Keys should be ascii strings and
        values should usually be ascii strings or numbers, but any type
        supported by the json library should be serialised OK. If you pass
        "timestamp", "host" or "filename" as keys, they will replace the
        default values of those keys.
    plot_kst : boolean or string, optional
        If True, a kst process will be spawned to plot the data in realtime
        if a string is provided, KST will use a saved session at that path
    """

    def __str__(self):
        return type(self).__name__ + ' ' + self.shortname

    def __init__(self, filename, quantites, append=False, overwrite=False, metadata=None, plot_kst=False):
        self._plot_kst = plot_kst
        self.quantities = quantites
        self.file = None
        self.columns = ['Time_elapsed']
        self.column_units = ['s']
        self._has_stopped = False

        self._metadata = {'timestamp': time.time(), 'host': gethostname(), 'filename': filename}
        if metadata is not None:
            self._metadata.update(metadata)
        self.start_time = self._metadata['timestamp']

        for quantity in self.quantities:
            if type(quantity.name) is list:
                self.columns = self.columns + quantity.name
                self.column_units = self.column_units + quantity.units
            else:
                self.columns.append(quantity.name)
                self.column_units.append(quantity.units)

        self.filename, self.shortname = self._clean_up_filename(filename)
        self._set_up_file(append, overwrite)

        recorder_registry[str(self)] = self
        self._start()

    def _clean_up_filename(self, filename):
        dirname, filename = os.path.split(filename)
        short_name, file_ext = os.path.splitext(filename)
        if dirname:
            if not os.path.exists(dirname):
                raise ValueError("The filename includes a non-existent directory")
        else:
            dirname = os.getcwd()
        if not file_ext:
            file_ext = '.csv'
        new_filename = os.path.join(dirname, short_name + file_ext)
        return new_filename, short_name

    def _set_up_file(self, append, overwrite):
        """Find right filename, open file, write titles etc. if necessary"""
        new_title_line = ", ".join(self.columns)
        if append:
            if os.path.isfile(self.filename):
                with open(self.filename, 'r', newline='') as oldfile:
                    old_first_line = oldfile.readline().strip()
                    if old_first_line[0] == '{':
                        old_metadata = json.loads(old_first_line)
                        old_title_line = oldfile.readline().strip()
                    else:
                        old_metadata = None
                        old_title_line = old_first_line
                if old_title_line == new_title_line:
                    _logger.info("Starting '" + str(self) +
                                 "' appending to existing file with Quantities: " + new_title_line)
                    if old_metadata is not None:
                        self._metadata = old_metadata
                    self.start_time = self._metadata['timestamp']
                    self._file = open(self.filename, 'a+', newline='')
                    self._writer = csv.writer(self._file)
                    return
                else:
                    _logger.warn("Could not append to file: titles don't match. Starting new file.")
            else:
                _logger.warn("Could not append to file: file not found. Starting new file.")
        if os.path.isfile(self.filename):
            if overwrite:
                _logger.info("Starting '" + str(self) + "' overwriting existing file with Quantities: "
                             + new_title_line)
            else:
                n = 1
                name, ext = os.path.splitext(self.filename)
                while os.path.isfile(name + f'_{n}' + ext):
                    n += 1
                self.filename = name + f'_{n}' + ext
                _logger.warn("'" + str(self) + f"' added suffix _{n}, as the requested file already exists")
                _logger.info("Starting '" + str(self) + "' writing new file with Quantities: " + new_title_line)
        else:
            _logger.info("Starting " + str(self) + ' writing new file with Quantities: ' + new_title_line)
        self._file = open(self.filename, 'w+', newline='')
        self._file.write(json.dumps(self._metadata) + '\n')
        self._file.write(new_title_line + '\n')
        self._writer = csv.writer(self._file)
        self._writer.writerow(self.column_units)

    def _start(self):
        self._start_time = time.time()
        if self._plot_kst:
            self.open_kst()

    def open_kst(self):
        "Open a KST plot of the file being recorded"
        try:
            datafile_path = os.path.join(os.getcwd(), self.filename)
            if isinstance(self._plot_kst, str):
                subprocess.Popen([kst_binary, self._plot_kst, "-F", datafile_path])
            else:
                layoutargs = ['-x', 'Time_elapsed']
                for col in self.columns[1:]:
                    layoutargs += ['-y', col]
                subprocess.Popen([kst_binary, datafile_path] + layoutargs)
        except Exception as e:
            _logger.error(str(self) + " failed to launch KST subprocess")
            _logger.error(str(self) + " Error was: " + str(e))

    def record_line(self):
        """ Measure all the `Quantitiy`s and add the values to the file."""
        try:
            values = [time.time() - self.start_time]
            for ix_quant, quantity in enumerate(self.quantities):
                try:
                    if type(quantity.name) is list:
                        values = values + quantity.value
                    else:
                        values.append(quantity.value)
                except Exception:
                    _logger.error(f"Recorder failed to get value from Quantity '{quantity.name}', using NaN")
                    values = values + [np.nan] * np.size(quantity.name)
            self._writer.writerow(values)
            self._file.flush()
        except Exception:
            _logger.error("Error in Recorder.record_line(). A line will be missing", exc_info=True)

    def record_timed_lines(self, number, interval):
        """Record `number` lines with `interval` second gaps. See also: recorders.AutoRecorder"""
        for line in range(number):
            time.sleep(interval)
            self.record_line()

    def stop(self):
        """ Stop the Recorder and close the file """
        self._file.close()
        if self._has_stopped:
            _logger.warning("Tried to stop " + str(self) + "but it is already stopped")
        else:
            _logger.info("Stopping " + str(self))
            del recorder_registry[str(self)]
            self._has_stopped = True


class AutoRecorder(Recorder):
    """
    An automatic version of the Recorder which runs in its own thread

    This works the same way as the Recorder class, but instead of adding a line
    to the file every time `record_line` is called, it adds a line every
    `interval` seconds.

    Parameters
    ----------
    interval : number
        The time to wait between lines in the file, in seconds. The total time
        will be this plus the time taken to measure all the quantities.

    All other parameters are the same as the `Recorder` class
    """

    def __init__(self, filename, quantites, interval, **kwargs):
        self._stopping = False
        self._paused = False
        self.interval = interval

        def callback():
            while not self._stopping:
                if not self._paused:
                    self.record_line()
                # Many short sleeps not one long one so we pick up interval changes.
                interval_start = time.time()
                while time.time() - interval_start < self.interval:
                    time.sleep(min(self.interval, 1))

        self._thread = ThreadWithExcLog(target=callback,
                                        name="AutoRecorder:" + filename)
        super().__init__(filename, quantites, **kwargs)

    def _start(self):
        """Start recording."""
        super()._start()
        self._thread.start()

    def pause(self):
        """Pauses recording, continue with .resume()."""
        self._paused = True

    def resume(self):
        """Continues a recording after a .pause()."""
        self._paused = False

    def stop(self):
        """Stop Recording and clean up. Blocks until done."""
        self._stopping = True
        self._thread.join()
        super().stop()
