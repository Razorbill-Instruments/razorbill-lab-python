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
import threading
import subprocess
import os
import time
import numpy as np
from . import _logger

KST_BINARY = r'C:\UnmanagedBinaries\KST2_2019-02-06_17-17\bin\kst2.exe'

recorder_registry = {}


class Recorder():
    """
    Record several `Quantity`s and write them to a file.

    Opens a CSV file and writes column headers into it.  Each time
    `record_line` is called, it will get the value of each quanity and add them
    to the file as a new line.

    Construction
    ------------
    filename : string, required
        filename, without extension, to write the data to
    quantities : itterable, required
        the ``Quantity``s to record.  If there is only one, put it in a list
    overwrite : boolean, optional
        If true, and the file already exists, it will be overwritten.
    plot_kst : boolean or string, optional
        If True, a kst process will be spawned to plot the data in realtime
        if a string is provided, KST will use a saved session at that path
    """

    def __str__(self):
        return type(self).__name__ + ' ' + self.filename + '.csv'

    def __init__(self, filename, quantites, overwrite=False, plot_kst=False):
        self._plot_kst = plot_kst
        self.quantities = quantites
        self.filename = filename
        if not overwrite:
            filenumber = 0
            while os.path.isfile(self.filename + '.csv'):
                filenumber += 1
                self.filename = filename + '_' + str(filenumber)
                _logger.warn(str(self) + " added suffix, as the requested file already exists")
        recorder_registry[str(self)] = self
        self._start()

    def _start(self):
        logstr = "".join(["{}, ".format(q.name) for q in self.quantities])
        _logger.info("Starting " + str(self) + ' with Quantities: ' + logstr)
        self._file = open(self.filename + '.csv', 'w', newline='')
        self.columns = ['Time_Elapsed']
        self.column_units = ['s']
        for quantity in self.quantities:
            if type(quantity.name) is list:
                self.columns = self.columns + quantity.name
                self.column_units = self.column_units + quantity.units
            else:
                self.columns.append(quantity.name)
                self.column_units.append(quantity.units)
        self.writer = csv.writer(self._file)
        self.writer.writerow(self.columns)
        self.writer.writerow(self.column_units)
        self._start_time = time.time()
        if self._plot_kst:
            try:
                datafile_path = os.path.join(os.getcwd(), self.filename + '.csv')
                if isinstance(self._plot_kst, str):
                    subprocess.Popen([KST_BINARY, self._plot_kst, "-F", datafile_path])
                else:
                    layoutargs = ['-x', 'Time_Elapsed']
                    for col in self.columns[1:]:
                        layoutargs += ['-y', col]
                    subprocess.Popen([KST_BINARY, datafile_path] + layoutargs)
            except Exception as e:
                _logger.error(str(self) + " failed to launch KST subprocess")
                _logger.error(str(self) + " Error was: " + str(e))

    def record_line(self):
        """ Measure all the `Quantitiy`s and add the values to the file."""
        try:
            values = [time.time() - self._start_time]
            for quantity in self.quantities:
                try:
                    if type(quantity.name) is list:
                        values = values + quantity.value
                    else:
                        values.append(quantity.value)
                except Exception:
                    _logger.error("Recorder failed to get value from Quantity, using NaN")
                    values = values + [np.nan] * np.size(quantity.name)
            self.writer.writerow(values)
            self._file.flush()
        except Exception as e:
            _logger.error("Error in Recorder.record_line(). A line will be missing")
            _logger.error(str(e))

    def stop(self):
        """ Stop the Recorder and close the file """
        self._file.close()
        _logger.info("Stopping " + str(self))
        del recorder_registry[str(self)]


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
        self._interval = interval

        def callback():
            while not self._stopping:
                if not self._paused:
                    self.record_line()
                time.sleep(self._interval)
        self._thread = threading.Thread(target=callback,
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
        """Stop Recording and clean up. May block for up to interval."""
        self._stopping = True
        self._thread.join()
        super().stop()
