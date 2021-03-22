#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing a dummy instrument which is actually the python shell.
Useful for testing
"""

from . import Instrument, ChildInstrument, _logger, _scpi_property
import random
import threading
import time


class _Child(ChildInstrument):
    """ An example of a child which could be e.g. an input or an output on an
    instrument which has more than one.
    """
    number_property = _scpi_property('CH{subaddr:}:FLOAT', '{:g}', doc="number")
    string_property = _scpi_property('CH{subaddr:}:STRING', '{}', doc="string")
    bool_property = _scpi_property('CH{subaddr:}:BOOL', '{:bool}', doc="bool")
    list_property = _scpi_property('CH{subaddr:}:LIST', '{:g},{:bool},{}', doc="num,bool,string")


class Dummy(Instrument):
    """
    Dummy
    =====

    Interface to a dummy instrument.

    In addition to the methods and properties detailed below, it inherits
    a number of both from the Instrument class. Unlike most Instruments
    there is no check that this is real - because it isn't.  Reads and
    writes are redirected to the shell.

    Construction
    ------------
    ``dum = Dummy('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'DUMMY1::INSTR'``


    Methods
    -------
    None yet

    Dynamic Properties
    ----------
    None yet

    """
    _io_holdoff = 0.1

    def __init__(self, visa_name):
        """ This is a dummy which does not actually use VISA
        Arguments:
            visa_name: Visa name like 'DUMMY::INSTR'
        """
        self._visa_name = visa_name
        self._pyvisa = None
        self._sub_address = None
        self._last_io_time = 0
        self.lock = threading.RLock()
        self._climber = 0
        self._decay = 1
        self._num_faults = 0
        _logger.info("Connected to " + str(self))
        self.children = {1: _Child(self, 1), 2: _Child(self, 2), 3: _Child(self, 3)}
        self._is_frozen = True

    def raw_write(self, string):
        """Write string to the instrument."""
        with self.lock:
            while time.time() - self._last_io_time < self._io_holdoff:
                time.sleep(self._io_holdoff/5)
                print("io too fast")
            print("Dummy at {} >>> {}".format(self._visa_name, string))
            self._last_io_time = time.time()

    def raw_read(self):
        """Read string from the instrument."""
        with self.lock:
            while time.time() - self._last_io_time < self._io_holdoff:
                time.sleep(self._io_holdoff/5)
                print("io too fast")
            ans = input("Dummy at {} <<< ".format(self._visa_name)).strip()
            self._last_io_time = time.time()
            return ans

    def climber():
        def getter(self):
            self._climber += 1
            return self._climber
        return getter

    def decay():
        def getter(self):
            self._decay *= 0.9
            return self._decay + 1
        return getter

    def rand():
        def getter(self):
            return random.random()
        return getter

    def one():
        def getter(self):
            return 1
        return getter

    def dodgy():
        def getter(self):
            if random.random() > 0.2:
                return self._num_faults
            else:
                self._num_faults += 1
                raise RuntimeError('Test exception handling')
        return getter

    random_num = property(rand())
    climbing_num = property(climber())
    decay_num = property(decay())
    dodgy_num = property(dodgy())
    number_property = _scpi_property('FLOAT', '{:g}', doc="number")
    string_property = _scpi_property('STRING', '{}', doc="string")
    bool_property = _scpi_property('BOOL', '{:bool}', doc="bool")
    list_property = _scpi_property('LIST', '{:g},{:bool},{}', doc="num,bool,string")
    one = property(one())
