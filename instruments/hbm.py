# -*- coding: utf-8 -*-
"""
Module for interfacing with products from HBM (who have rebranded as HBK)
It includes the load cell controller ClipX used for the load test rig
"""

from . import Instrument, WrongInstrumentError, BadCommandError, _make_getter
import time
from measurement import ThreadWithExcLog


class ClipX(Instrument):
    """
    ClipX load cell controller
    =====

    Interface to a ClipX load cell contoller. It's slow to start and get
    an IP address, so give it time.

    The contoller has quite a lot of advancned functionality, which can be
    configured via a web browser. It also supports TEDS so can download
    calibration data automatically and give reading in units of N

    The browser connection to ClipX is at http://ClipX.local

    The browser interface can be used at the same time as the python connection.
    You need to log in to access some functions. The passwords are blank.

    Settings for clipx can be saved, see "parameter sets". There is a saved
    parameter set for the load test rig, it includes some DIO functions
    used to protect the load cell form overloading.

    It is possible to regularily read a FIFO buffer, so that no data is
    missing. It is not implemnted yet.

    Connections are automatically closed after 30 sec inactivity, so a thread
    is used to keep it open by taking and dropping measurements.

    Construction
    ------------
    ``lc = ClipX('visa_name')``

    visa_name : string, required
        The IP address and port of the instrument, e.g.
        ``'TCPIP0::169.254.119.2::55000::SOCKET'``
        you can get the IP address from the web interface, but you ahve to log
        in as an admin (blank password)


    Methods
    -------
    tare() : tare the load cell
        .

    tare_reset() : cancel the tare function
        .

    Dynamic Properties
    ----------
    force_filtered : Force, in Newtons, after tare and filtering
        use this for force most of the time.  It has been filtered
        according to the filter configuration for "calculated value 1" in the
        browser interface.

    force_gross : Force in Newtons, before tare and filtering
        Use if you need to check the load cell is not being overloaded.

    force_net : Force in Newtons, after tare but before filtering
        Use this if looking for higher frequency components in the force
        signal. This signal is normally lowpass filtered at 100 Hz, but can be
        configured on the amplifier page of the web interface.

    """

    _idnstring = "153"

    def _setup(self):
        """ Configure ethernet, and start keep-alive thread. The device needs
        real messages to stay on line: normal ethernet keep-alive packets
        are not enough"""
        self._pyvisa.read_termination = '\n'
        self._pyvisa.write_termination = '\n'
        def poll_device():
            while(True):
                self.force_gross
                time.sleep(10)
        clipx_keepalive_thread = ThreadWithExcLog(target=poll_device,
                                                  name="clipx_keepalive")
        clipx_keepalive_thread.start()

    def write(self, message):
        resp = self.raw_query(message)
        if (resp.startswith("?")):
            raise BadCommandError(f"ClipX did not understand '{message}'. "
                                  + "The message may be malformed or "
                                  + "contain an illegal parameter value.")

    def _check_idn(self):
        """override the IDN function, as the instrument does not use *IDN?"""
        resp = self.raw_query('SDO? 0x4300,13')
        if not resp.startswith(self._idnstring):
            raise WrongInstrumentError("Wrote 'SDO? 0x4300,13' (HBM type ID"
                                       + " request) Expected response starting"
                                       + "'{}'got '{}'".format(self._idnstring, resp))

    force_gross = property(_make_getter("SDO? 0x44f0,4", "{:g}"), None)
    force_net = property(_make_getter("SDO? 0x44f0,5", "{:g}"), None)
    force_filtered = property(_make_getter("SDO? 0x44f0,22", "{:g}"), None)

    def tare(self):
        self.write("SDO 0x4411,4,0")

    def tare_reset(self):
        self.write("SDO 0x4411,8,0")

    def set_limit_switch(self, switch, val1, val2):
        """Set the limits switch levels.

        If the switch is set up for under or over, then val1 is the level
        and val2 is the hysteresis about that level.  If the switch is
        set up for in-band or out-of-band, then val 1 is the bottom of the band
        and val2 is the width of the band.

        Leave switch 1 at Gross, out-of-band, -205 to +205. This is to protect
        the load cell. The other switches are available for user configuration.
        Usually switch 2 is Net, out-of-band, -55 to +55 to protect the cell
        and should be adjusted to suit the stress or strain cell in the jig.
        """
        switch = int(switch)
        if not (2 <= switch <= 4):
            raise ValueError(f"Tried to set limit switch #{switch}, There are 4, and #1 is reserved")
        val1 = float(val1)
        val2 = float(val2)
        self.write(f"SDO 0x4604,{switch},{val1}")
        self.write(f"SDO 0x4605,{switch},{val2}")
