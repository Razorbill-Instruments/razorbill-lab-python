#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Keithley 2100 series digital multimeters
"""

from . import ScpiInstrument, _scpi_property
import math


class TSP01(ScpiInstrument):
    """
    TSP01
    ============

    Interface to the Thor Labs humidity and temperature dongle.

    In addition to the methods and properties detailed below, it inherits
    a number of both from the Instrument class. When created, the object
    immediately contacts the instrument at the given visa address, and checks
    that it is present and identifies itself correctly.

    Construction
    ------------
    ``tsp = TSP01('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'USB0::0x1313::0x80F8::M00490648::INSTR'``


    Methods
    -------
    None yet

    Dynamic Properties
    ----------
    temperature_internal : float, get only
        Measures the temperature, in degrees C
    temperature_external_1 : float, get only
        Measures the temperature, in degrees C
    temperature_external_2 : float, get only
        Measures the temperature, in degrees C
    humidity : float, get only
        humidity in % rel
    humidity_abs : float, get only
        absolute humidity in hPa water vapour. Calculated from self.temperature_internal
        and self.humidity using WMO method.
    """

    _idnstring = "Thorlabs,TSP01,"

    temperature_internal = _scpi_property('SENS1:TEMP:DATA', '{:g}', can_set=False)
    temperature_external_1 = _scpi_property('SENS3:TEMP:DATA', '{:g}', can_set=False)
    temperature_external_2 = _scpi_property('SENS4:TEMP:DATA', '{:g}', can_set=False)
    humidity = _scpi_property('SENS2:HUM:DATA', '{:g}', can_set=False)

    @property
    def humidity_abs(self):
        """Calculate absolute humidity (in hPa) from other readings."""
        # For conversion method, see the "guide to Instruments and Methods of Observation"
        # by the World Meteorological Organization (WMO), 2018 edition, annex 4.B
        t = self.temperature_internal
        h = self.humidity
        e_sat = 6.112 * math.exp(17.62 * t / (243.12 + t))
        e = e_sat * h / 100
        return e
