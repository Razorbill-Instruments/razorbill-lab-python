#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Keysight products
"""

from . import ScpiInstrument, _scpi_property


class E4980A(ScpiInstrument):
    """Keysight E4980[A|AL] LCR meter"""

    _idnstring = ["Keysight Technologies,E4980", "Agilent Technologies,E4980"]

    meas = _scpi_property('FETCH', '{:g},{:g},+0', doc="cap and loss",
                          can_set=False)
    freq = _scpi_property('FREQ', '{:g}', doc="set in Hz")
    ex_volt_set = _scpi_property('VOLT:LEV', '{:g}', doc="Target Excitation voltage")
    ex_volt_act = _scpi_property('FETC:SMON:VAC', '{:g}', doc="Actual Excitation voltage")
    meas_time = _scpi_property('APER', '{}', doc="one of LONG, MED, SHORT")
    mode = _scpi_property('FUNC:IMP:TYPE', '{}', doc='one of CPD,CPQ,CPG,'
                          'CPRP,CSD,CSQ,CSRS,LPD,LPQ,LPG,LPRP,LPRD,LSD,LSQ,'
                          'LSRS,LSRD,RX,ZTD,ZTR,GB,YTD,YTR,VDID')

    @property
    def meas_all(self):
        """Include exc. voltage, in case that is useful for debugging down the line"""
        meas = self.meas
        volt_act = self.ex_volt_act
        return meas + [volt_act]

    def recall_A(self):
        self.raw_write("MMEM:LOAD:STAT:REG 0")

    def recall_B(self):
        self.raw_write("MMEM:LOAD:STAT:REG 1")

    def setdefaults(self):
        self.freq = 100000
        self.mode = "CPD"
        self.ex_volt_set = 2
        self.meas_time = "LONG"

    def abort_meas(self):
        """Restarts measurement.

        Assuming the bridge is in continuous measurement mode (internal trigger) this will
        abort the current measurement and restart. Useful after e.g. a multiplexer change.
        """
        self.raw_write("ABOR")
        self.raw_write("TRIG:SOUR INT")


class U1241C(ScpiInstrument):
    """ Keysight U1241C handheld DMM"""

    _idnstring = "Keysight Technologies,U1241C"

    def raw_query(self, string):
        """ override the raw query function to add clearing of buffer, necessary
        because the device sends unsolicited mesages when the mode is changed
        (they start with a * )"""
        with self.lock:
            self._pyvisa.clear()
            self.raw_write(string)
            return self.raw_read()

    """return the reading as shown on the main display. (Set what to read using
    the roatry switch). Returns +9.90000000E+37 for Overload, may give odd
    readings when autoranging"""
    read = _scpi_property('READ', '{:g}', can_set=False)

    """get the conf string, so you can throw an error if the front panel switch
    is set wrong. The conf string includes range info, but decoding this isn't
    implemnted yet, it's just dropped.

    This isn't foolproof, as the CONF string is just CURR for several current
    modes, and the leads need to be in the right place too.

    Possible responses are VOLT, VOLT:AC, RES, CONT, DIOD, CAP, TEMP:K, CURR,
    CURR:AC, CPER:4-20mA. Menu diving might make temperatures in C and F
    available, along with a 0-20mA loop percentage in place of the 4-20"""
    raw_conf = _scpi_property('CONF', '"{}"', can_set=False)
    @property
    def conf(self):
        confstring = self.raw_conf
        mode = confstring.split(" ")[0]
        return(mode)

    def check_conf(self, wanted_conf):
        """ user freindly wrapper for above"""
        while 1:
            actual_conf = self.conf
            if actual_conf == wanted_conf:
                return
            else:
                input("The meter is set to {} not {} correct it and press "
                      "enter to continue".format(actual_conf, wanted_conf))

    """ check the battery level (0 to 1)"""
    batt = _scpi_property('SYST:BATT', '{:%}', can_set=False)

    """there are some other commands, not yet implemented. I don't have a
    programming manual but going by a forum post, it supports at least the
    following:
    *RST?
    *CLS
    ABOR
    CALC:PEAK?
    CALC:AVER?
    CONF?
    FETC?
    INIT
    READ?
    STAT?
    SYST:BATT?
    TRIG:SOUR
    TRIG:REF:COUN
    some of which probaby correspond to in-built data-logging"""
