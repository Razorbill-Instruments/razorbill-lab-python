#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Keithley 2100 series digital multimeters
"""

from . import ScpiInstrument, _scpi_property

class Keithley2100(ScpiInstrument):
    """
    Keithley2100
    ============
    
    Interface to a Keithley 2100 series digital multimeter.
    
    In addition to the methods and properties detailed below, it inherits
    a number of both from the Instrument class. When created, the object
    immediately contacts the instrument at the given visa address, and checks
    that it is present and identifies itself correctly.
    
    Construction
    ------------
    ``meter = Keithley2100('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'USB0::0x05E6::0x2100::1416334::INSTR'``


    Methods
    -------
    None yet
    
    Dynamic Properties
    ----------
    temperature : float, get only
        Measures the temperature, in degrees C, of the connected RTD.
        
    """
    
    _idnstring = "KEITHLEY INSTRUMENTS INC.,MODEL 2100"
    
    temperature = _scpi_property('MEAS:TEMP', '{:g}', can_set=False)    
    voltage = _scpi_property('MEAS:VOLT', '{:g}', can_set=False)
    current = _scpi_property('MEAS:CURR', '{:g}', can_set=False)