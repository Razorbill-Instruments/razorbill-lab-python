#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for reading from Edwards vacuum guages

"""
#TODO this whole module might make more sense with a seperate method that
# parses the repsonses, spitting at space and ; and maybe also handles the
# read/write stuff

from . import Instrument, WrongInstrumentError
from measurement import ThreadWithExcLog
import parse
import numpy as np
from scipy.interpolate import interp1d
import time

class AbnormalResponse(Exception):
    """ The guage responeded with an abnormal aknowlagement or
    status bits, any data supplied cannot be trusted"""
    pass

class nAPG(Instrument):
    """
    Edwards nAPG active Digital Pirani guage
    ========================================

    Module for reading pressure from a guage with RS232 interface. Please note
    this guage requires a custom cable as it uses a non-standard pinout for
    the DB9 connector on the guage. A separate power supply is also required
    and connects to the custom cable.

    Construction
    ------------
    ``vac = nAPG('visa_name', quiet=True)``

    visa_name : string, required
        The address of the instrument, e.g. ``'COM1'``

    quiet: bolean, True to supress communication errors

    Methods
    -------
    None yet

    Dynamic Properties
    ----------
    pressure (float, get only)

    Other functions are availabe but not yet implemented, see guage instruction
    manual. The RS485 version of the guage may work or may need tweaks.

    """
    def __init__(self, visa_name, quiet=True):
        """override init to add quiet variable, then call the normal init"""
        self.quiet = quiet
        super().__init__(visa_name)

    _idnstring = "=S0 nAPG-LC_RS232;"
    normal_status = "0014" # may be 0014 or 0010 depending on set point output

    def _setup(self):
        """ Configure serial """
        self._pyvisa.read_termination = '\r'
        self._pyvisa.write_termination = '\r'
        self._pyvisa.baud_rate = 9600

    def write(self, message):
        """ use this in stead of raw_write, as the gauge aknowlages commands.
        I'm not overriding raw_write as this would break raw_query"""
        resp = self.raw_query(message)
        if self.quiet == False:
            if resp.split()[1] != "0":
                raise AbnormalResponse("""The guage aknowlaged a serial write
                       with '{}' in stead of 0. Consult the gauge manual for more
                       information""".format(resp))
        return

    def _check_idn(self):
        """override the IDN function, as the instrument does not use *IDN?"""
        resp = self.raw_query('?S0')
        if not resp.startswith(self._idnstring):
            raise WrongInstrumentError("""Wrote "?S0" (Edwards guage
                        identification request) Expected response starting '{}'
                        got '{}'""".format(self._idnstring, resp))

    def _config(self):
        """ override the _config hook to ensure units are set to mbar"""
        self.write("!S755 1") # 1=mbar, 2=Pascal, 3=Torr
        self.write("!S756 0") # set the gas type to air while I'm here

    @property
    def pressure(self):
        """ get the pressure response and optionally check the status bits"""
        resp = self.raw_query("?V752")
        # response format is =cmd pressure;bits
        resp = resp.split()
        resp = resp[1].split(';')
        if self.quiet == False:
            if resp[1] != self.normal_status:
                raise AbnormalResponse("""The guage status bits were '{}'
                       when '{}' is normal. Consult the gauge manual for more
                       information""".format(resp[2], self.normal_status))
        return float(resp[0])


class nEXT(Instrument):
    """
    Edwards nEXT Turbomolecular Pump
    ================================
    module for controling the pump and reading health data over RS-232. The
    pump uses a custom D-Sub 15 cable, which is conveted to standard serial
    but the ports in the pumping battery power supply. The wiring in the
    power supply also links pins to set the pump in serial mode

    Construction
    ------------
    ``turbo = nEXT('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'COM1'``

    Methods
    -------
    start() : no argument, returns nothing
        start the turbopump. if the pump is in a fail state, you need to call
        stop first to clear the fail state
    stop() : no arguments, returns nothing
        stop the pump, also clears fail states to allow a restart

    Dynamic properties
    ------------------
    temperatures : rotor, motor and motor controller

    pump_hours : service reccomended at 20k

    pump_cycles : start-stop cycle count, for fategue risk

    status_bytes : general status monitoring, parsing not yet implemented

    TODO - start and stop fan

    Other functions are availabe but not yet implemented, see pump instruction
    manual.
    """

    _idnstring = "=S851 nEXT-P1"

    def _setup(self):
        """ Configure serial """
        self._pyvisa.read_termination = '\r'
        self._pyvisa.write_termination = '\r'
        self._pyvisa.baud_rate = 9600

    def write(self, message):
        """ use this in stead of raw_write, as the gauge aknowlages commands.
        I'm not overriding raw_write as this would break raw_query"""
        self.raw_query(message)
        #TODO check the reply is as expected, see todo at top
        return

    def _check_idn(self):
        """override the IDN function, as the instrument does not use *IDN?"""
        resp = self.raw_query('?S851')
        if not resp.startswith(self._idnstring):
            raise WrongInstrumentError("""Wrote "?S851" (Edwards pump
                        identification request) Expected response starting '{}'
                        got '{}'""".format(self._idnstring, resp))

    def start(self):
        """ start the  pump (if pump stopped due to a fail state call stop()
        to clear the fail state first). Also starts the cooling fan"""
        self.write ("!S864 8")
        self.write("!C852 1")

    def stop(self):
        """stop the pump, will also clear fail states. Also stops the cooling
        fan (after 5 minuite delay, threaded into the background)"""
        self.write("!C852 0")
        def fan_run_on():
            time.sleep(600)
            self.write("!S864 10")
        fan_run_on_thread = ThreadWithExcLog(target=fan_run_on,
                                             name="Turbo fan run on")
        fan_run_on_thread.start()


    """Rotor speed in Hz, the max for this pump is 1500"""
    @property
    def speed(self):
        resp = self.raw_query('?V852')
        result = parse.parse("=V852 {:g};{:x}",resp)
        return result[0]

    @property
    def temperatures(self):
        """"get temperatures in degrees C, returns a list as
        [motor, controller, rotor]"""
        resp = self.raw_query('?V865')
        result = parse.parse("=V865 {:g};{:g};{:g}",resp)
        return [result[0],result[1],result[2]] # result is an object from parse

    @property
    def motor_parameters(self):
        """get motor drive parameters, returned as a list
        [voltage,current,power] (units are volts, amps, watts)"""
        resp = self.raw_query("?V860")
        result = parse.parse("=V860 {:g};{:g};{:g}",resp)
        params = [result[0],result[1],result[2]] # result is an object from parse
        for i in [0,1,2]: params[i] = params[i]/10
        return params

    @property
    def pump_hours(self):
        """get hours run. Service every 35k hours"""
        resp = self.raw_query("?V862")
        result = parse.parse("=V862 {:g}",resp)
        return result  [0]

    @property
    def pump_cycles(self):
        """get the number of start-stop cycles.  new rotor recomended at 20k"""
        resp = self.raw_query("?V884")
        result = parse.search("=V884 {:g};{:g}",resp)
        return result[0]

    @property
    def status_bytes(self):
        """get the status bytes, expressed as an int"""
        resp = self.raw_query("?V852")
        result = parse.search("=V852 {:g};{:x}",resp)
        return result[1]


class nAIM_P():
    """
    Edwards AIM-S high vacuum guage
    ================================
    This is not an instrument, as the guage isn't connected to the computer.
    it contains a method for converting voltage to pressure. The voltage value
    must first be obtained from another instrument with an analog input
    (probaby the CTC100)
    """

    def __init__(self, quantity):
        self.quantity = quantity

    #table format is [volts,mbar]
    caltable = np.array([[2,   1e-8  ],
                         [2.5, 2.4e-8],
                         [3,   5.8e-8],
                         [3.2, 8.1e-8],
                         [3.4, 1.1e-7],
                         [3.6, 1.5e-7],
                         [3.8, 2.1e-7],
                         [4,   2.9e-7],
                         [4.2, 4e-7  ],
                         [4.4, 5.4e-7],
                         [4.6, 7.3e-7],
                         [4.8, 9.8e-7],
                         [5,   1.3e-6],
                         [5.2, 1.7e-6],
                         [5.4, 2.2e-6],
                         [5.6, 2.8e-6],
                         [5.8, 3.6e-6],
                         [6,   4.5e-6],
                         [6.2, 5.6e-6],
                         [6.4, 6.9e-6],
                         [6.6, 8.4e-6],
                         [6.8, 1e-5  ],
                         [7,   1.2e-5],
                         [7.2, 1.4e-5],
                         [7.4, 1.7e-5],
                         [7.6, 2e-5  ],
                         [7.8, 2.4e-5],
                         [8,   2.9e-5],
                         [8.2, 3.5e-5],
                         [8.4, 4.3e-5],
                         [8.6, 5.7e-5],
                         [8.8, 7.9e-5],
                         [9,   1.2e-4],
                         [9.2, 1.9e-4],
                         [9.4, 3.3e-4],
                         [9.6, 6.7e-4],
                         [9.8, 1.7e-3],
                         [9.9, 3.6e-3],
                         [10, 1e-2   ]])

    #this is a callable!
    interpolator = interp1d(caltable[:,0], caltable[:,1], kind='cubic')

    @property
    def pressure(self):
        voltage = self.quantity.value
        if (-0.1 < voltage < 2): return 1000
        if (10 < voltage): return 1000
        if (np.isnan(voltage)): return 1000
        pressure = float(self.interpolator(voltage))
        return pressure
