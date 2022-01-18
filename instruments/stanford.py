#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with equiptment from Stanford Reseach systems
 -> Stanford SR830 Lock in amplifiers.
 -> Stanford CTC100 cryogenic temperature controller
"""

from . import Instrument, ScpiInstrument, ChildInstrument, \
                _make_setter, _make_getter, _scpi_property
import bisect
import numpy as np


class StanfordSR830(ScpiInstrument):
    """
    StanfordSR830
    =============

    Interface to a Stanford model SR830 lock-in amplifier

    In addition to the methods and properties detailed below, it inherits
    a number of both from the Instrument class. When created, the object
    immediately contacts the instrument at the given visa address, and checks
    that it is present and identifies itself correctly.

    Construction
    ------------
    ``lia = StanfordSR830('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'ASRL5::INSTR'``


    Methods
    -------
    auto_sens() : returns nothing
    auto_reserve() : returns nothing
    next_sens(value) : returns int
    next_time_const(value) : returns int

    Properties
    ----------
    meas_x : Get only, float
        measures the current X value, in volts
    meas_y : Get only, float
        measures the current Y value, in volts
    meas_r : Get only, float
        measures the current R value, in volts
    meas_t : Get only, float
        measures the current \theta value, in degrees

    ref_phas : Get and set, float
        The refernce phase, in degrees
    ref_freq : Get and set, float
        The refernce frequency, in Hz
    ref_harm : Get and set, float
        The reference harmonic, 1 means fundamental
    ref_ampl : Get and set, float
        The amplitude of sine out. 4mV to 5V with 2mV resolution
    ref_internal : Get and Set, boolean
        Use internal reference if true, external reference if false
    ref_ext_mode : Get and Set, int
        Type of ext ref. 0 = Sine, 1 = Rising TTL, 2 = falling TTL

    input_mode : Get and set, int
        Input terminal configuation. 0 = A, 1 = A-B, 2 = I(1M), 3 = I(100M)
    input_ground : Get and set, boolean
        Input terminal shell. True = Ground, False = float
    input_dc_coupled : get and set, boolean
        Input coupling, True = AC coupled, False = DC coupled
    input_line_filter : get and set, int
        Line filter configuration. 0 = none, 1 = line, 2 = 2*line, 3 = both

    demod_sens : Get and set, int
        Sensitivity, a n int between 0(2nV) and 26(1V)
    demod_reserve : Get and set, int
        Dynamic reserve, 0 = high, 1 = medium, 2 = low
    deomd_time_const : get and set, int
        Time constant, an int between 0(10us) and 19 (30ks)

    """

    _idnstring = "Stanford_Research_Systems,SR830"

    def _setup(self):
        """Instrument needs different settings for RS232 and GPIB, this
        function guesses which we are using and sets things correctly.
        GPIB not tested.
        """
        if self._visa_name.startswith('ASRL'):
            self._pyvisa.read_termination = '\r'
            self.raw_write('OUTX 0')
        elif self._visa_name.startswith('GPIB'):
            self._pyvisa.read_termination = '\n'
            self.raw_write('OUTX 1')
        else:
            raise ValueError('Could not identify bus from resource name')

    def auto_sens(self):
        """ Automatically set sensitivity based on signal right now"""
        self.raw_write('AGAN')

    def auto_reserve(self):
        """ Automatically set reserve based on signal right now """
        self.raw_write('ARSV')

    # dicts for sensitivity and time constant lookup
    _sensitivities = (2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9, 1e-6,
                      2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6, 1e-3,
                      2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3, 1)
    _time_constants = (10e-6, 30e-6, 100e-6, 300e-6,
                       1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3,
                       1, 3, 10, 30, 300,
                       1e3, 3e3, 10e3, 30e3)

    def next_sens(self, value):
        """Returns the index of the lowest sensitivity larger than value

        e.g. demod_sens = next_sens(1.25e-3)"""
        return bisect.bisect_left(self._sensitivities, value)

    def next_time_const(self, value):
        """Returns the index of the lowest time constant larger than value

        e.g. demod_time_const = next_time_const(700e-3)"""
        return bisect.bisect_left(self._time_constants, value)

    # measured result properties
    meas_x = property(_make_getter('OUTP? 1', '{:g}'))
    meas_y = property(_make_getter('OUTP? 2', '{:g}'))
    meas_r = property(_make_getter('OUTP? 3', '{:g}'))
    meas_t = property(_make_getter('OUTP? 4', '{:g}'))

    # sine out and ref channel properties
    ref_phas = _scpi_property('PHAS', '{:g}')
    ref_freq = _scpi_property('FREQ', '{:g}')
    ref_harm = _scpi_property('HARM', '{:d}')
    ref_ampl = _scpi_property('SLVL', '{:g}')
    ref_internal = _scpi_property('FMOD', '{:bool}')
    ref_ext_mode = _scpi_property('RSLP', '{:d}')

    # Input mode properties
    input_mode = _scpi_property('ISRC', '{:d}')
    input_ground = _scpi_property('IGND', '{:bool}')
    input_dc_coupled = _scpi_property('ICPL', '{:bool}')
    input_line_filter = _scpi_property('ILIN', '{:d}')

    # Demodulator properties
    demod_sens = _scpi_property('SENS', '{:d}')
    demod_reserve = _scpi_property('RMOD', '{:d}')
    demod_time_const = _scpi_property('OFLT', '{:d}')


class _CTC100_Input(ChildInstrument):
    """ a thermometer input channel for the CTC100"""
    value = property(_make_getter('in{subaddr}.Value?', '{:g}'))


class _CTC100_AIO(ChildInstrument):
    """ an analog input input channel for the CTC100. make sure the relevent
    AIO is configured for input or output through the front panel. Outputs can
    be get or set, but don't set an input"""
    # TODO work out what happens if you try to set an input
    voltage = property(_make_getter('AIO{subaddr}.Value?', '{:g}'),
                       _make_setter('AIO{subaddr}.Value', '{:g}'))


class _CTC100_Output(ChildInstrument):
    """ a output output channel for the CTC100"""
    ramp = property(_make_getter('Out{subaddr}.PID.Ramp?', '{:g}'),
                    _make_setter('Out{subaddr}.PID.Ramp', '{:g}'))
    target = property(_make_getter('Out{subaddr}.PID.RampT?', '{:g}'),
                      _make_setter('Out{subaddr}.PID.RampT', '{:g}'))
    setpoint = property(_make_getter('Out{subaddr}.PID.Setpoint?', '{:g}'),
                        _make_setter('Out{subaddr}.PID.Setpoint', '{:g}'))
    power = property(_make_getter('Out{subaddr}.value?', '{:g}'),
                     _make_setter('Out{subaddr}.value', '{:g}'))


class CTC100(Instrument):
    """Stanford CTC100 Cryogenic Temperature Controller

    This instrument has a lot of commands availabe and one can also upload
    macros that can then be executed as commands. This module currently only
    has the basics.

    The instrument can be connected by RS232, USB, Ethernet or GPIB.  This
    module only tested for USB for now.

    It is a good idea to set system->verbose->low from the front panel.

    Construction
    ------------
    ``ctc = CTC100('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'com4'``

    Properties
    ----------
    output_enable : bool
        enable or disable all heaters and analog outs.

    inputs[n].value : float
        where n is a thermometer channel 1 to 4. units: as per setting on
        instrument. Get only
    output[n].setpoint : float
        where n is output channel 1 or 2. Units: K. Use the front panel
        interface to link the output to the relevent thermometer
    output[n].ramp : float
        where n is output channel 1 or 2. units: K/sec. set to 0 for unlimited
        ramp rate
    all_vals : list of floats (may be nan)
    all_val_names : list of strings
    all_val_units : list of strings
        These three are a list of parameters measured by the instrument,
        including input temperatures, output powers, AIO values and severeral
        more note reported elsewhere such as heater resistances. Exactly what
        is included depends on congifuration of the instrument.
    """
    _idnstring = "Stanford Research Systems, CTC100 Cryogenic Temperature Controller"

    def _setup(self):
        self._pyvisa.encoding = 'cp437'
        self.inputs = {1: _CTC100_Input(self, 1),
                       2: _CTC100_Input(self, 2),
                       3: _CTC100_Input(self, 3),
                       4: _CTC100_Input(self, 4)}
        self.outputs = {1: _CTC100_Output(self, 1),
                        2: _CTC100_Output(self, 2)}
        self.analog = {1: _CTC100_AIO(self, 1),
                       2: _CTC100_AIO(self, 2),
                       3: _CTC100_AIO(self, 3),
                       4: _CTC100_AIO(self, 4)}

    def raw_read(self):
        """Override to strip non-ascii chars"""
        ans = super().raw_read()
        return ans.replace('\u03A9', 'ohm')

    @property
    def output_enable(self):
        resp = self.raw_query('OutputEnable?')
        if resp.lower().strip("'") == "on":
            return True
        if resp.lower().strip("'") == "off":
            return False
        else:
            raise ValueError(f"Could not parse response '{resp}' from CTC100")

    @output_enable.setter
    def output_enable(self, boolean):
        if boolean:
            s = "on"
        else:
            s = "off"
        self.raw_write(f'outputEnable {s}')

    @property
    def all_vals(self):
        resp = self.raw_query('getOutput?')
        return np.genfromtxt(resp.split(','))

    @property
    def all_val_names(self):
        resp = self.raw_query('getOutput.names?')
        resp_list = [r.strip() for r in resp.split(',')]
        return resp_list

    @property
    def all_val_units(self):
        resp = self.raw_query('getOutput.units?')
        resp_list = [r.strip() for r in resp.split(',')]
        resp_list = ['-' if unit == '' else unit for unit in resp_list]
        return resp_list
