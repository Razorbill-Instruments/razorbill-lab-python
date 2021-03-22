#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with GW Instek instruments
"""


from . import ScpiInstrument, _scpi_property
from parse import search

class LCR6000(ScpiInstrument):
    """ GW Instek LCR6000 series meter"""
    
    _idnstring = "LCR-6"
    
    def _setup(self):
        self._pyvisa.baud_rate = 115200
    
    freq = _scpi_property('FREQ', '{:g}', doc= "set in Hz")
    ex_volt_set = _scpi_property('VOLT:LEV', '{:g}', doc= "Excitation voltage")
    meas_time = _scpi_property('APER', '{}', doc = "one of SLOW, MED, FAST")
    mode = _scpi_property('FUNC', '{}', doc="""one of Cs-Rs, Cs-D, Cp-Rp, Cp-D,
                          Lp-Rp, Lp-Q, Ls-Rs, Ls-Q, Rs-Q, Rp-Q, R-X, DCR, Z-thr,
                          Z-thd, Z-D, Z-Q.""")
                          
    def get_meas(self):
        resp = self.raw_query("FETCH?")
        parsed = search("{:g},{:g},", resp)
        if parsed == None:
            raise IOError('Could not parse the response "{}" from the instrument'.format(resp))
        if len(parsed.fixed) == 1:
            return parsed.fixed[0]
        else:
            return list(parsed.fixed)
        
    meas = property(get_meas, doc="cap and loss")

    def recall(self, num):
        self.raw_write(f"FILE:LOAD {num}")
