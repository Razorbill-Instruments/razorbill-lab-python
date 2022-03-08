#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Modue for interfacing with Razorbil Instruments production grade products.
Rough prototypes and one-off lab equipment live in homemade.
"""

from . import ScpiInstrument, ChildInstrument, _scpi_property
import time


class _RP100_Channel(ChildInstrument):
    """
    An output subsystem on an RP100 power supply
    """
    enable = _scpi_property('OUTP{subaddr:}', '{:bool}', doc="Output relay status")

    voltage_set = _scpi_property('SOUR{subaddr:}:VOLT', '{:g}', doc="Target voltage")
    slew_rate = _scpi_property('SOUR{subaddr:}:VOLT:SLEW', '{:g}', doc="Slew rate")
    voltage_now = _scpi_property('SOUR{subaddr:}:VOLT:NOW', '{:g}', doc="Voltage right now")
    meas_voltage = _scpi_property('MEAS{subaddr:}:VOLT', '{:g}', can_set=False, doc="Measured load voltage")
    meas_current = _scpi_property('MEAS{subaddr:}:CURR', '{:g}', can_set=False, doc="Measured load current")

    def wait_for(self):
        while not self.is_done:
             time.sleep(0.05)

    def safe_disable(self):
        """Ramp the voltage to zero and disable. Kinder to piezos than enable=False."""
        old_slew = self.slew_rate
        self.slew_rate = 50
        self.voltage_set = 0
        self.wait_for()
        self.enable = False
        self.slew_rate = old_slew

    @property
    def is_done(self):
        return self.voltage_now == self.voltage_set


class RP100(ScpiInstrument):
    """RP100 Power Supply."""

    _idnstring = "Razorbill,RP100,"

    def _setup(self):
        self.channels = {1: _RP100_Channel(self, 1), 2: _RP100_Channel(self, 2)}

    error_count = _scpi_property('SYST:ERR:COUN', '{:d}', can_set=False, doc="Number of errors in the error queue")
    error = _scpi_property('SYST:ERR', '{:d},{}', can_set=False, doc="Oldest error as a (number, description) list")


    def wait_for(self):
        """Call wait_for on each channel."""
        self.channels[1].wait_for()
        self.channels[2].wait_for()

    @property
    def is_done(self):
        """Return True only when both channels are done."""
        return self.channels[1].is_done and self.channels[2].is_done


class MP240(ScpiInstrument):
    """MP240 multiplexer.

    Construction
    ------------
    ``mux = MP240('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'COM1'``

    Methods
    -------
    cycle() : no argument, does not return
        cycles through channels at 0.5 sec interval (Ctrl+C to stop)

    Dynamic Properties
    ------------------

    output : int, 0 to 4
        set 0 (all off) or 1-4. The chosen channel will be exclusivly set
    h1 to h4 : bool
        set individaul relays in the high bank
    l1 to l4 : bool
        set individual relays in the low bank

    several dianostic and error fucntions also implemented, see module
    """

    _idnstring = "Razorbill,MP240"

    error_count = _scpi_property('SYST:ERR:COUN', '{:d}', can_set=False,
                                 doc="Number of errors in the error queue")
    error = _scpi_property('SYST:ERR', '{:d},{}', can_set=False,
                           doc="Oldest error as a (number, description) list")
    
    output = _scpi_property('SELE', '{:g}', doc="output to enable, use 0 for all off")

    h1 = _scpi_property("H1", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    l1 = _scpi_property("L1", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    h2 = _scpi_property("H2", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    l2 = _scpi_property("L2", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    h3 = _scpi_property("H3", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    l3 = _scpi_property("L3", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    h4 = _scpi_property("H4", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")
    l4 = _scpi_property("L4", "{:bool}", doc="set individual realys, 1 = connected, 0 = grounded")

    external_control_mode = _scpi_property("MODE:EXT", "{:bool}")
    relay_external_power = _scpi_property("MODE:PWRS", "{:bool}")

    def _cycle(self):
        for ch in [1, 2, 3, 4]:
            self.output = ch
        time.sleep(0.5)
    
