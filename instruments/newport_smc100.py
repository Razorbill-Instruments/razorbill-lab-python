#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Newport SMC100 motor drives
"""

from . import Instrument, WrongInstrumentError, _getfloat

class NewportSMC100(Instrument):
    """
    NewportSMC100
    =============

    Interface to a Newport SMC100 motor drive for positioning stages

    In addition to the methods and properties detailed below, it inherits
    a number of both from the Instrument class. When created, the object
    immediately contacts the instrument at the given visa address, and checks
    that it is present and identifies itself correctly.

    Construction
    ------------
    ``lia = NewportSMC100('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'ASRL5::INSTR'``


    Methods
    -------



    Properties
    ----------

    """
    
    def _setup(self):
        """ Configure serial """
        self._pyvisa.read_termination = '\r\n'
        self._pyvisa.write_termination = '\r\n'
        self._pyvisa.baud_rate = 57600

    def _check_idn(self):
        self.raw_write('1ID?') # uses this not '*IDN?'
        resp = self.raw_read()
        # note this returns the ID of the stage, not the controller, and
        # the SMC sontroller works with many stages. The echoed command
        # can be used to ID this as a newport system of some kind though.
        if not resp.startswith('1ID'):
            raise WrongInstrumentError(
                'Wrote "1ID?" Expected respose starting "1ID" got "{}"'.format(resp))

    def raw_read(self):
        """This override is necessary to strip the echoed command"""
        with self.lock:
            return self._pyvisa.read().strip()[3:]

    def find_home(self):
        """Initialise the hardware and find zero point"""
        self.raw_write('1OR')

    def go_absolute(self, position):
        """Go to an absolute position measured in mm from black end"""
        self.raw_write('1PA{0:.8f}'.format(position))

    def go_relative(self, position):
        """Go to an relative position measured in mm from current position"""
        self.raw_write('1PR{0:.8f}'.format(position))

    # Read only properties
    setpoint = property(_getfloat('1TH'))
    position = property(_getfloat('1TP'))

