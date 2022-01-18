#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
instruments module. Provides the Instrument and ScpiInstrument abstract
classes for actual instruments to subclass. Also defines a few other
useful classes such as Exceptions that Instruments might want to raise.
"""

import pyvisa
import threading
import parse
import time
from measurement import _rootlogger

_logger = _rootlogger.getChild('instruments')

instrument_registry = {}
""" This dict will hold all connected instruments, keys are VISA addresses."""


class WrongInstrumentError(Exception):
    """The wrong instrument is connected

    A connection was successfully established, and the instrument responded
    to a request to identify itself, but the ID received was wrong.
    Probably the instrument at the given VISA identifier is not the one
    you wanted.
    """
    pass

class InstrumentSaysNo(Exception):
    """For some reason, the instrument did not do what the message asked.

    Where the reason for non-compliance is known, consider using
    InstrumentConfigError or BadCommandError instead.
    """
    pass

class InstrumentConfigError(InstrumentSaysNo):
    """The instrument can't comply due to a configuration error.

    Raise this when IO completed OK, but the instrument can't do what it was
    asked to do, e.g. you have tried to set a value on a digital IO which is
    configured for input, or an instrument is disabled by a switch or digital
    enable input.
    """
    pass

class BadCommandError(InstrumentSaysNo):
    """The message sent to the instrument was malformed or has a bad parameter.

    Raise this when IO completed OK, but the command was not recognised,
    or otherwise rejected by the instrument
    """
    pass


class _Multiton(type):
    """ Metaclass for creating multitions. A new object will only be created
    if there is not another object of the class with the same VISA address in
    the instrument_registry
    Adapted from stackoverflow http://stackoverflow.com/questions/3615565/
    """
    def __call__(cls, visa_name, *args, **kwargs):
        try:
            resource_manager = pyvisa.ResourceManager()
            visa_name = resource_manager.resource_info(visa_name).resource_name
        except pyvisa.VisaIOError:
            # Not a valid visa address. Use it anyway, it might be a non-visa multiton instrument
            # but even if it is a bad value, it is better to fail in __init__ than here
            visa_name = visa_name.upper()
        if visa_name not in instrument_registry:
            self = cls.__new__(cls, visa_name, *args, **kwargs)
            cls.__init__(self, visa_name, *args, **kwargs)
            instrument_registry[visa_name] = self
        else:
            _logger.debug("Reusing existing " + str(instrument_registry[visa_name]))
        return instrument_registry[visa_name]


class _Freezable():
    """Class which will not allow new attributes to be added accidentally.

    This is mostly for classes which will be used from the interactive
    interpreter, where it is easy to add a new attrubute by accident when
    trying to set one.  To use this, subclass it and add `self._is_frozen = True`
    at the end of __init__
    """
    _is_frozen = False

    def __setattr__(self, key, value):
        if self._is_frozen and key not in dir(self):
            raise TypeError(("Tried to add new attribute '{}' to {}. If you actually"
                             " want that set _is_frozen to False".format(key, self)))
        object.__setattr__(self, key, value)


class Instrument(_Freezable, metaclass=_Multiton):
    """Instrument abstract class; subclass this to make an instrument.

    Sensible default methods are provided, they should work for most instruments.
    The constructor includes a check of the instrument's *IDN?, the subclass
    must set _idnstring for this to work.
    Since this has the Multiton metaclass, it and any subclass will only allow
    new objects to be created if they have a new VISA address, otherwise you'll
    get the existing object with that VISA address.
    This also has functionality to prevent new attributes being added at
    runtime, to protect against typos.
    """
    _idnstring = ""
    # 1ms minimum between IO ops. Override as necessary
    _io_holdoff = 1 / 1000
    # instument will be disconnected after this many consecutive io failures. Override with None to disable.
    _max_io_fails = 10

    def __str__(self):
        return type(self).__name__ + ' instrument at ' + self._visa_name

    def __init__(self, visa_name):
        """ Connects to the instrument and checks that it is the right one.
        Arguments:
            visa_name: Visa name like 'ASRL3::INSTR'
        """
        self._visa_name = visa_name
        self.lock = threading.RLock()
        self._sub_address = None
        self._last_io_time = 0
        self._num_io_fails = 0
        self._pyvisa = None
        self.connect()
        self._is_frozen = True

    def _setup(self):
        """ Override to do extra setup before checking connection.
        Typically used by serial instruments to set baud rate etc. Can also be
        used to assemble an Instrument object from ChildInstrument objects
        """
        pass

    def _check_idn(self):
        """Query the instrument *IDN? and check it is as expected"""
        resp = self.raw_query('*IDN?')
        if not isinstance(self._idnstring, list):
            self._idnstring = [self._idnstring]
        for idn in self._idnstring:
            if resp.startswith(idn):
                return
        raise WrongInstrumentError(
                """Wrote "*IDN?" Expected response starting
                '{}' got '{}'""".format(self._idnstring[0], resp))

    def _config(self):
        """override this method to configure the instrument after the
        connection is open.
        """
        pass

    def connect(self):
        "Connect to the instrument. Called automatically during __init__"
        resource_manager = pyvisa.ResourceManager()
        with self.lock:
            self._pyvisa = resource_manager.open_resource(self._visa_name)
            self._pyvisa.encoding = "cp1252"  # Change in setup() if necessary
            self._setup()
            self._check_idn()
            self._config()
            _logger.debug("Connected to " + str(self))

    def disconnect(self):
        """Disconnect from the instrument"""
        try:
            # Depending on the state it is in, this may or may not work.
            self._pyvisa.close()
        except pyvisa.VisaIOError:
            pass
        self._pyvisa = None
        _logger.debug("Disconnected from " + str(self))

    def raw_write(self, string):
        """Write string to the instrument."""
        with self.lock:
            if self._pyvisa is None:
                return
            while time.time() - self._last_io_time < self._io_holdoff:
                time.sleep(self._io_holdoff / 5)
            try:
                self._pyvisa.write(string)
                self._last_io_time = time.time()
                self._num_io_fails = 0
            except pyvisa.VisaIOError as e:
                if (self._max_io_fails is not None) and (self._num_io_fails < self._max_io_fails):
                    self._num_io_fails += 1
                else:
                    self.disconnect()
                    _logger.error(f"{self._num_io_fails} IO errors on {str(self)}, disconnecting. "
                                  + "Fix the problem then use self.connect() to get it back")
                raise e

    def raw_read(self):
        """Read string from the instrument."""
        with self.lock:
            if self._pyvisa is None:
                return None
            while time.time() - self._last_io_time < self._io_holdoff:
                time.sleep(self._io_holdoff / 5)
            try:
                ans = self._pyvisa.read().strip()
                self._last_io_time = time.time()
                self._num_io_fails = 0
                return ans
            except pyvisa.VisaIOError as e:
                if (self._max_io_fails is not None) and (self._num_io_fails < self._max_io_fails):
                    self._num_io_fails += 1
                else:
                    self.disconnect()
                    _logger.error(f"{self._num_io_fails} IO errors on {str(self)}, disconnecting. "
                                  + "Fix the problem then use self.connect() to get it back")
                raise e

    def raw_query(self, string):
        """Write string then read from the instrument"""
        # not using pyvisa.query as some instruments may override one
        # but not the other of these - e.g. Newport SMC100
        with self.lock:
            self.raw_write(string)
            return self.raw_read()


class ScpiInstrument(Instrument):
    """Extends the Instrument abstract class to make an abstract class for
    instruments which implement the core SCPI commands, such as *cls, *rst
    and so forth.
    """

    def reset(self):
        """Reset instrument to power on settings"""
        self.raw_write('*RST')

    def status_clear(self):
        """Clear status bytes"""
        self.raw_write('*CLS')


class ChildInstrument(_Freezable):
    """ Used for sub-instruments, such as a module in a mainframe (where
    the module doesn't have a separate VISA address) or a channel in a multi-
    channel instrument
    """

    def __str__(self):
        return (type(self).__name__ + " at subaddr=" + str(self._sub_address)
                + " on " + str(self.parent))

    def __init__(self, parent, sub_address):
        self.parent = parent
        self._sub_address = sub_address
        self._is_frozen = True

    def raw_write(self, *args, **kwargs):
        self.parent.raw_write(*args, **kwargs)

    def raw_read(self, *args, **kwargs):
        return self.parent.raw_read(*args, **kwargs)

    def raw_query(self, *args, **kwargs):
        return self.parent.raw_query(*args, **kwargs)


def _make_setter(command, fmt="{}"):
    """Return a setter for use with property().

    command is a SCPI string, such as 'SOUR:AMPL'
    fmt is as per str.format().
        use '{:d}' for boolean int
        use '{},{},{}' or similar if setting a tuple
    parent can be used to climb up a self.parent.parent... tree.
    """

    def scpi_setter(self, value):
        if not type(value) == list:
            value = [value]
        fixed_fmt = fmt.replace('{:bool}', '{:d}')
        set_string = fixed_fmt.format(*value)
        command_string = command.format(subaddr=self._sub_address)
        self.raw_write(command_string + ' ' + set_string)
    return scpi_setter


def _make_getter(command, format):
    """ return a getter for use with property().

    command is a SCPI string, such as 'KELVIN?'
    format is as per str.format() or parse.parse()
        use {:d},{:s} etc. for tuples
        use {:bool} for booleans. False if '0', else true
    """
    def bool_parser(string):
        return not string.strip() == '0'

    def scpi_getter(self):
        resp = self.raw_query(command.format(subaddr=self._sub_address))
        parsed = parse.parse(format, resp, dict(bool=bool_parser))
        if parsed is None:
            raise IOError('Could not parse the response "{}" from the instrument'.format(resp))
        if len(parsed.fixed) == 1:
            return parsed.fixed[0]
        else:
            return list(parsed.fixed)

    return scpi_getter


def _scpi_property(command, fmt, doc="", can_get=True, can_set=True):
    """ Make property from SCPI command"""
    if can_get:
        getter = _make_getter(command + "?", fmt)
    else:
        getter = None
    if can_set:
        setter = _make_setter(command, fmt)
    else:
        setter = None
    return property(getter, setter, None, doc)
