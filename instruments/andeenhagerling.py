#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#

"""
Module for interfacing with an AH2xxx series capacitance bridge.
Needs a null modem cable or adapter.
Doesn't always work out of the box. Different bridges seem to have 
slightly different behaviour.
"""

from . import ScpiInstrument, _make_getter
import pyvisa.constants
from pyvisa import VisaIOError
from parse import search


class AH2550(ScpiInstrument):

    # Some instruments seem to support IDN and some dont.
    #_idnstring = "MANUFACTURER    ANDEEN-HAGERLING"
    _idnstring = "ILLEGAL WORD: *IDN?"

    def _check_idn(self):
        return # Todo fix this
        """Query the instrument *IDN? and check it is as expected"""
        # This override is required as the bridge gives a multiline response
        # including the termchar at the end of each line.
        self._flush_buffer()
        super()._check_idn()
        self._flush_buffer()

    def _setup(self):
        # Required to stop the bridge echoing things
        self._pyvisa.set_visa_attribute(pyvisa.constants.VI_ATTR_ASRL_FLOW_CNTRL,
                                        pyvisa.constants.VI_ASRL_FLOW_XON_XOFF)
        self._pyvisa.write_termination = '\r'
        self._pyvisa.timeout = 20000
        self.raw_write("SERIAL .....0")      # switch off serial echo
        self.raw_write("UNITS 1")            # set units 1=nS, 4=Gohm
        self.raw_write("FIELD 0.0.9.9.0.0")  # Set response format
        self._flush_buffer()

    def _flush_buffer(self):
        # Empty the transmit buffer on the instrument
        # TODO: improve. This is truly horrible.
        try:
            while True:
                self.raw_read()
        except VisaIOError:
            pass

    def _get_measurement(self):
        resp = self.raw_query('SI')
        cap = search('C={:^g}PF', resp)
        loss = search('L={:^g}NS', resp)
        return (cap.fixed[0], loss.fixed[0])

    def _set_sample(self, sample):
        self.raw_write("SAMPLE {}".format(sample))

    sample = property(None, _set_sample, doc="Sample switch setting")

    meas = property(_get_measurement,
                    doc="capacitance and loss")
