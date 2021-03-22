#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Tek AFG3000 series arb waveform gens
"""

from . import ScpiInstrument, ChildInstrument, _scpi_property

class _Channel(ChildInstrument):
    """Class represents one channel on a multichannel instrument. See parent
    instrument for complete documentation.
    """

    def phase_sync(self):
        """Sync channel 2 phase with channel 1 and with TTL"""
        self.raw_write('SOUR{subaddr:}:PHAS:INIT')

    amplitude = _scpi_property('SOUR{subaddr:}:VOLT:AMPL', '{:g}', doc="Amplitude in Volts")
    offset = _scpi_property('SOUR{subaddr:}:VOLT:OFFS', '{:g}', doc="Offset in volts, DC amplitude")
    frequency = _scpi_property('SOUR{subaddr:}:FREQ', '{:g}', doc="Frequency in Hz")
    phase_radians = _scpi_property('SOUR{subaddr:}:PHAS', '{:g}', doc="Phase in Radians")
    impedance = _scpi_property('OUTP{subaddr:}:IMP', '{:g}', doc="Output impedance, can be numpy inf")
    enable = _scpi_property('OUTP{subaddr:}:STAT', '{:bool}', doc="Output Enable")
    waveform = _scpi_property('SOUR{subaddr:}:FUNC', '{}', doc="Waveform, e.g. dc sin ramp squ ...")
    limit_max = _scpi_property('SOUR{subaddr:}:VOLT:LIM:HIGH', '{:g}', doc="Upper voltage safety limit")
    limit_min = _scpi_property('SOUR{subaddr:}:VOLT:LIM:LOW', '{:g}', doc="Lower voltage safety limit")

class TekAFG3000(ScpiInstrument):
    """
    TekAFG3000
    ==========

    Interface to a Tek AFG3000 series arb waveform generator

    TODO: make adjustments for 1 channel instrument, currently assumes 2

    In addition to the methods and properties detailed below, it inherits
    a number of both from the Instrument class. When created, the object
    immediately contacts the instrument at the given visa address, and checks
    that it is present and identifies itself correctly.

    Construction
    ------------
    ``source = TekAFG3000('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'ASRL5::INSTR'``


    Methods
    -------


    Dynamic Properties
    ----------

    """
    def __init__(self, visa_name, num_channels=2):
        # FIXME: Use weakrefs to clean up circular refs on deletion
        super().__init__(visa_name)
        self.chs = {}
        for n in range(1, num_channels+1):
            self.chs[n] = _Channel(self, n)

