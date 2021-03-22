#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Lakeshore temperature controllers.

Currently contains classes for models 218 and 340. It should be relatively easy 
to add more, as most of them use the same commands, albeit with different
numbers of control loops, inputs etc.
"""

import pyvisa
from . import ScpiInstrument, ChildInstrument, _scpi_property, _make_getter, _make_setter


class _Input(ChildInstrument):
    """
    Class for input channels in a Lakeshore instrument, providing properties for
    temperature etc. Each LakshoreXXX object should have a dict of inputs
    and the number of inputs may vary from object to object if the instrument
    they represent has option cards installed.
    This class can be used directly in classes for simple controllers (e.g.
    model 218) or subclassed for more complex controllers (e.g. model 370)
    """
    sensor_reading = property(_make_getter('SRDG? {subaddr:}', '{:g}'))
    kelvin = property(_make_getter('KRDG? {subaddr:}', '{:g}'))

class _Loop(ChildInstrument):
    """ A control loop on a Lakeshore.  There may be one, several or none"""
    pid = property(_make_getter('PID? {subaddr:}', '{:g},{:g},{:g}'),
                   _make_setter('PID {subaddr:},', '{:g},{:g},{:g}'))
    setpoint = property(_make_getter('SETP? {subaddr:}', '{:g}'),
                        _make_setter('SETP {subaddr:},', '{:g}'))
    ramp = property(_make_getter('RAMP? {subaddr:}', '{:bool},{:g}'),
                    _make_setter('RAMP {subaddr:},', '{:bool},{:g}'))
    ramp_in_progress = property(_make_getter('RAMPST? {subaddr:},', '{:bool}'))


class Lakeshore218(ScpiInstrument):
    """
    Class for a Lakeshore model 218 temperature monitor
    """
    def _setup(self):
        """ Configures serial and creates inputs
        """
        # FIXME: Use weakrefs to clean up circular refs on deletion
        self._pyvisa.parity = pyvisa.constants.Parity.odd
        self._pyvisa.data_bits = 7
        self.inputs = {1:_Input(self, '1'), 2:_Input(self, '2'),
                       3:_Input(self, '3'), 4:_Input(self, '4'),
                       5:_Input(self, '5'), 6:_Input(self, '6'),
                       7:_Input(self, '7'), 8:_Input(self, '8'),
                      }

    _idnstring = "LSCI,MODEL218"
    _io_holdoff = 50/1000 # wait 50ms between reads/writes

    def _check_idn(self):
        # This is here because the 218 has failing NOVRAM and is unable to
        # identify itself without parity errors.
        # FIXME: Replace NOVRAM in the 218
        pass


class Lakeshore340(ScpiInstrument):
    """
    Class for a Lakeshore model 340 temperature controller
    """
    def __init__(self, visa_name, extra_inputs=None):
        """ Connects to the instrument and checks that it is the right one.
        Arguments:
            visa_name: Visa name like 'ASRL1::INSTR'
        """
        # This override is needed so that we can get the right number of inputs
        # set up if the instrument has the optional extra inputs
        # FIXME: Use weakrefs to clean up circular refs on deletion
        super().__init__(visa_name)
        self.inputs = {'A':_Input(self, 'A'), 'B':_Input(self, 'B')}
        if extra_inputs:
            if extra_inputs == "3462":
                self.inputs['C'] = _Input(self, 'C')
                self.inputs['D'] = _Input(self, 'C')
            else:
                raise NotImplementedError("Extra input card {} not yet implemented".format(extra_inputs))

    def _setup(self):
        """ Configure serial interface """
        self._pyvisa.parity = pyvisa.constants.Parity.odd
        self._pyvisa.data_bits = 7
        self.loops = {1:_Loop(self, 1), 2:_Loop(self, 2)}
        
    _idnstring = "LSCI,MODEL340"
    _io_holdoff = 50/1000 # wait 50ms between reads/writes

    heater_power = _scpi_property('HTR?', '{:g}', can_set=False)
    heater_range = _scpi_property('RANGE', '{:d}')


class Lakeshore331(ScpiInstrument):
    """
    Class for a Lakeshore model 331 temperature controller
    """
    def _setup(self):
        """ Configure serial interface """
        self._pyvisa.parity = pyvisa.constants.Parity.odd
        self._pyvisa.data_bits = 7
        self.loops = {1:_Loop(self, 1), 2:_Loop(self, 2)}
        
    _idnstring = "LSCI,MODEL331"
    _io_holdoff = 50/1000 # wait 50ms between reads/writes

    heater_power = _scpi_property('HTR?', '{:g}', can_set=False)
    heater_range = _scpi_property('RANGE', '{:d}')