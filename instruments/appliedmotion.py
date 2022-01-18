#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with applied motion products. The implemented
instrument is a stepper motor controller.
"""

from . import Instrument,  _make_getter, _logger
from . import WrongInstrumentError, InstrumentConfigError, BadCommandError
import time
from pyvisa import VisaIOError


def _make_setter(command, fmt="{}"):
    """similar the one in instuments, but without ? on queries."""
    def setter(self, value):
        if not type(value) == list:
            value = [value]
        fixed_fmt = fmt.replace('{:bool}', '{:d}')
        set_string = fixed_fmt.format(*value)
        command_string = command.format(subaddr=self._sub_address)
        self.write(command_string + ' ' + set_string)
    return setter


class ST5Q(Instrument):
    """
    ST5-Q motor driver
    =====

    Interface to an ST5-Q stepper motor contoller.

    Only basic commands for direct control of the motor are implemented here.

    The communications seem poorly documented, you may need to send HR to
    start a sesion and QT will close a session.

    If extending this module to query registers, be aware that some values are
    stored in different units than the instructions used to write them.

    Configuring the Drive
    ---------------------

    The drive can be configured and controlled using ST configurator and
    Q programmer, which are availabe from the Applied Motion website and
    at Z:\\Manuals Utilities and Drivers\\applied motion stepper

    The Q functionality allows the driver to remember settigns and routines.
    Take care that it is set correctly for your application that you don't
    overwrite a routine that someone else wants to keep.

    It is important to set the correct current limit, or the motor may be
    damaged. The correct limit for a nanotec L2018s0604-T3,5x1-25
    linear acctuator is 0.6A.

    The correct motion mode for RS232 control is SCL/Q, the command mode
    is point to point postioning. Respond with ack and nack should be checked

    Construction
    ------------
    ``motor = ST5Q('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'COM1'``


    Methods
    -------
    TBC

    Dynamic Properties
    ----------
    TBC

    """

    def _setup(self):
        """ Configure serial """
        self._pyvisa.read_termination = '\r'
        self._pyvisa.write_termination = '\r'
        self._pyvisa.baud_rate = 9600

    def write(self, message):
        resp = self.raw_query(message)
        if (resp == "%"):  # Ack for executed messages
            return None
        if (resp == "*"):  # Ack for buffered messages
            return None
        if (resp.startswith("?")):
            raise BadCommandError(f"The contoller Nacked. The message was'{message}'. The controller replied '{resp}'. "
                                  + "The message may be malformed or contain an illegal parameter value. If there's a "
                                  + "number after the question mark, refer to the host command reference p300 for "
                                  + "interpretation.")
        else:
            return resp  # it was a wanted response, not just an ack

    _idnstring = "?"

    def _check_idn(self):
        """override the IDN function, as the instrument does not use *IDN?
        using HR will start a serial session"""
        resp = self.raw_query('HR')
        if not resp.startswith(self._idnstring):
            raise WrongInstrumentError("""Wrote "HR" (ST motor driver handshake)
                        Expected response starting '{}'
                        got '{}'""".format(self._idnstring, resp))

    def move_usteps(self, steps):
        """the driver counts 1 rotation as 20000 steps - 200 real steps
        each devided into 100 microsteps. Accepts negative numbers."""
        self.write("FL{}".format(round(steps)))

    move_speed = property(_make_getter("VE", 'VE={:g}'),
                          _make_setter("VE", '{:g}'),
                          doc="motor speed in revs/sec. from 0.0042 to 80, in increments of 0.0042 (rounded by drive).")

    accel = property(_make_getter("AC", 'AC={:g}'),
                     _make_setter("AC", '{:g}'),
                     doc="""accelleration speed in revs/sec/sec. from 0.167
                     to 5461, in increments of 0.167 (rounded by drive).""")

    continuous_run_speed = property(_make_getter("CS", 'CS={:g}'),
                                    _make_setter("CS", '{0:.5f}'),
                                    doc="motor speed in revs/sec when in continuous run mode. Does not persist "
                                        + "after exiting crm.")

    continuous_run_accel = property(_make_getter("JA", 'JA={:g}'),
                                    _make_setter("JA", '{:g}'),
                                    doc="acceleration speed in revs/sec/sec when in continuous run mode. "
                                        + "Should probably be set equal so self.accel")

    current_drive = property(_make_getter("CC", 'CC={:g}'),
                             _make_setter("CC", '{:g}'),
                             doc="drive current per winding, in Amps")

    current_idle = property(_make_getter("CI", 'CI={:g}'),
                            _make_setter("CI", '{:g}'),
                            doc="Idle current in Amps. automatically capped at 90% of drive current")

    _buffer_space = property(_make_getter("BS", 'BS={:g}'), None)

    @property
    def buffer_count(self):
        """ check how many commands are in the buffer. If it's not 0, the
        previous command(s) are not finished yet"""
        return int(63 - self._buffer_space)

    def enable(self):
        """Flush command queue, enable motor, apply idle current.

        It is safe to call this when already enabled. Controller may refuse to
        enable depending on configuration of hardware enable pin X3
        """
        self.abort()  # Anything in the buffer can be dropped.
        resp1 = self.write("ME")
        resp2 = None
        if self._pyvisa.bytes_in_buffer > 0:
            resp2 = self._pyvisa.read()
        if resp1 == "&" or resp2 == '&':
            raise InstrumentConfigError("The motor could not be software-enabled "
                                        "because the hardware enable pin is either"
                                        " mis-configured or keeping it disabled")

    def disable(self):
        """stops the current to the motor. This is a buffered command so will
        wait until previous commands have finished. To stop in a hurry, use
        abort() and then optionally disable()"""
        self.write("MD")

    def save_settings(self):
        """saves the speed, accelration, and current to non-volatile memory.
        Also saves some other settigns that are not implemented here, so use
        with caution if you have modified any settigns by writing directly"""
        permission = input("This function may wear out the NV memory if used "
                           "too much. Don't call it from a loop. \n\r"
                           "Do you wish to continue? (y/N)")
        assert((permission == "Y") | (permission == "y"))
        self.write("SA")

    def move_mm(self, mm):
        """this will be mm when using a nanotec LGA351S12-B-UIAP-038
        linear acctuator"""
        _logger.warning("ST5Q.move_mm is depreciated. it has moved to loadtest.")
        self.move_usteps(mm * 51_200 / 0.609)

    def move_turns(self, turns):
        """Turns assuming 256usteps/step and 200 steps/rev. CW is pos, CCW is neg."""
        self.move_usteps(turns * 51_200)

    def continuous_run(self, speed=0):
        """ run continuously until stopped by abort() or hardware pin disable

        Speed is in turns per seccond and can be negative to set direction,
        or 0 to pause. Once started, speed can be adjusted by modifying the
        continuous_run_speed variable, for example as part of a PID loop.

        When running continuously, other move commands will be ignored.
        """
        self.abort()
        self.write("CJ")
        self.continuous_run_speed = speed

    def abort(self):
        """stops movement with a controlled decelleration, and wipes the
        command buffer"""
        self.write("SK")

    def reset_alarms(self):
        """clears alarms. Alarms cause the red and geen LEDs to flash in
        sequence, refer to label on controller for meaning"""
        self.write("AR")

    def test(self):
        """alternates the motor 1 turn each way until broken by user (CRTL-C)"""
        self.move_speed = 5
        while(1):
            self.move_turns(1)
            time.sleep(0.5)
            self.move_turns(-1)
            time.sleep(0.5)
