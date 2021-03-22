#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with applied motion products. The implemented 
instrument is a stepper motor controller. 
"""

from . import Instrument, WrongInstrumentError



class ST5Q(Instrument):
    """
    Interface to an ST5-Q stepper motor contoller.

    Only basic commands for direct control of the motor are implemented.  
    the drive can be configured and controlled using ST configurator and 
    Q programmer, which are availabe from the Applied Motion website and 
    at Z:\Manuals Utilities and Drivers\applied motion stepper
    
    The Q functionality allows the driver to remember settigns and routines. 
    take care that it is set correctly for your application that you don't 
    overwrite a routine that someone else wants to keep
    
    It is important ot set the correct current limit, or the motor may be 
    damaged.
    
    The correct motion mode for RS232 control is SCL/Q, the command mode
    is point to point postioning. Respond with ack and nack should be checked
    
    The communications seem poorly documented, you need to send HR\r to 
    start a sesion and QT\r will close a session.

    Construction
    ------------
    ``motor = ST5('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'COM1'``


    Methods
    -------
    None yet

    Dynamic Properties
    ----------
    None yet

    """

    def _setup(self):
        """ Configure serial """
        self._pyvisa.read_termination = '\r'
        self._pyvisa.write_termination = '\r'
        self._pyvisa.baud_rate = 9600
     
    idnstring = "?"
    def _check_idn(self):
        """override the IDN function, as the instrument does not use *IDN?
        using HR will start a serial session"""
        resp = self.raw_query('HR')
        if not resp.startswith(self._idnstring):
            raise WrongInstrumentError("""Wrote "?S0" (Edwards guage 
                        identification request) Expected response starting '{}'
                        got '{}'""".format(self._idnstring, resp))
    
    def movesteps(self,steps):
        self.write("FL{}".format(steps))
    
    def movemm(self,mm):
        self.movesteps(mm/2000)