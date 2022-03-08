#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
""" Module for measuring things, and writing the results to file.

Designed to work well with the instruments module. Normal usage is to create
a Quantity for everything you want to measure and then start a Recorder to
measure to file.
"""

import numpy as np
import __main__
from ._logging import _setup_logging, _setup_exception_logging, _rootlogger
from ._logging import ThreadWithExcLog  # NOQA for export
from .config import data_path, log_path, kst_binary  # NOQA for export

_environment_is_setup = False
logger = _rootlogger.getChild('user')  # for use in scripts. Use _logger within module
_logger = _rootlogger.getChild('measurement')


def setup_environment(log_path=log_path):
    """Call this at the start of an experiment to set up logging."""
    global _environment_is_setup
    if not _environment_is_setup:
        _setup_logging(log_path)
        _setup_exception_logging()
        _environment_is_setup = True
    else:
        _logger.info("Measurement session continuing in existing log")


class Quantity():
    """
    A measurement quantity which is being measured or controlled.

    Each Quantity is a measurable variable such as time, temperature, voltage
    etc or a set of measurement variables which are measured together, such as
    capacitance and loss or amplitude and phase.
    It contains the python code needed to obtain the variable(s) and the
    metadata needed to understand it/them.

    Construction
    ------------
    name : String or itterable of strings, required
        A human readable name, will become the column header in a CSV file.
    source : callable, string, or tuple
        Where to get the data, a function, variable or attribute (see below)
    units : string or itterable of strings, required
        Example: 'Hz'. Will be written to the CSV file too
    scalefactor : number or itterable of numbers, optional
        The measured value will be multiplied by this before being returned
    skiptest : Boolean, optional
        Unless this is true, immediatly try getting data to test the source.
    quiet : Boolean, optional
        If an error occours while getting the value, quiet quantities will
        return np.NaN, not quiet ones log and then re-raise the exception.

    Data Source
    -----------
    The `source` can be one of three things:

    A callable :
        the callable will be called to obtain a value
    A string :
        The string should be the name of a variable in the __main__ namespace.
        Avoid using this if practical.
    A tuple :
        The first element is an object, the second is a string corresponding
        to an attribute of that object. Use with ``instrument.Instrument``s
    If the source is going to return a list, then each of name, units and
    scalefactor should be itterables, the same length as the list.

    Attributes
    ----------
    `name`, `units` and `scalefactor` are as per the constructor.

    value : anything
        The value of the quanitiy at the moment the property is accessed.
        Note that it may take several milliseconds to get it if it comes from
        an instrument which takes a physical measurment.
    """

    def __init__(self, name, source, units, scalefactor=1, skiptest=False, quiet=False):
        self.name = name
        self.units = units
        self.scalefactor = scalefactor
        self.quiet = quiet
        self._has_warned = False
        if isinstance(name, list):
            if not isinstance(units, list) or len(name) != len(units):
                raise TypeError('If name is a list, units must be a list of the same length.')
        if callable(source):
            self._get_value = source
            logstr = "callable " + str(source)
        elif type(source) is tuple and len(source) == 2:
            self._get_value = lambda: getattr(source[0], source[1])
            logstr = "attribute " + source[1] + " of " + str(source[0])
        elif type(source) is str:
            self._get_value = lambda: getattr(__main__, source)
            logstr = "variable " + source
        else:
            raise TypeError("source could not be converted to a callable")
        _logger.debug("Created new Quantity called " + str(self.name)
                      + " from " + logstr)
        # Verify that it works
        if not skiptest:
            val = self.value
            if isinstance(name, list):
                if not isinstance(val, list) or len(name) != len(val):
                    raise TypeError('If name is a list, the source must return a list of the same length.')

    @property
    def value(self):
        try:
            if type(self.name) is list:
                val = list(np.multiply(self._get_value(), self.scalefactor))
            else:
                val = self._get_value() * self.scalefactor
            self._has_warned = False
            return val
        except Exception as e:
            if self.quiet:
                if not self._has_warned:
                    _logger.warning(f"Error while evaluating measurement Quantity '{self.name}', "
                                    + "Will use NaN. This warning appears once per run of failures",
                                    exc_info=True)
                    self._has_warned = True
                if type(self.name) is list:
                    return [np.nan] * np.size(self.name)
                else:
                    return np.nan
            else:
                _logger.error(f"Error while evaluating measurement Quantity '{self.name}'",
                              exc_info=True)
                raise e


def quantity_from_scanner(scanner, suffixes=[" Cap", " Loss", " ExcVolt"], units=["pF", "-", "V"],
                          scalefactor=[1e12, 1, 1], skiptest=False):
    """Build a Quantity from a CapScanner or similar object."""
    q_titles = []
    q_units = []
    q_scalefactor = []
    for channel in range(len(scanner)):
        q_units = q_units + units
        q_scalefactor = q_scalefactor + scalefactor
        cap = scanner.labels[channel]
        q_titles = q_titles + [cap + suffixes[0], cap + suffixes[1], cap + suffixes[2]]
    q = Quantity(q_titles, scanner.measure_all, q_units, q_scalefactor, skiptest)
    return q


class Quant_Checker():
    def __init__(self, quant, limits, action=None, index=None):
        """Check a quantity and low a warning if it is outside set limits.

        Call `.check()` at e.g. 30 second intervals. If the quantity is outside
        the limits it will log a warning. If it stays outside limits, it will
        log further warnings with decreasing frequency. It will log an info
        when the quantity goes back in limits. Optionally, it can take an
        action when the quantity first goes outside limits.

        Parameters
        ----------
        quant : mesurement.Quantity
            The quantity to be checked.
        limits : itterable of two numbers (min, max)
            `quant` should stay between these values
        action : callable, optional
            Callable will be called when the `quant` goes outside `limits`. It
            would be prudent to include logging in the callable. The default,
            `None` means take no action.
        index : int, optional
            If `quant.value` returns a list, check the value at this index.
        """
        self.quant = quant
        self.limits = limits
        self.action = action
        self.index = index
        self.num_checks = 0
        self.num_failures = 0

    @classmethod
    def _is_pow_two(cls, number):
        """Check if the given integer is a power of two."""
        if number < 1 or not isinstance(number, int):
            return False
        # check if only one bit is set and that bit is first
        # e.g 8: 1000 & 0111 = 0000, 6: 0110 & 0101 = 0100
        return (number & (number-1) == 0)

    def check(self):
        """Perform check on quantity. Call e.g. every 30 sec."""
        self.num_checks += 1
        if self.index is None:
            value = self.quant.value
            name = self.quant.name
            units = self.quant.units
        else:
            value = self.quant.value[self.index]
            name = self.quant.name[self.index]
            units = self.quant.units[self.index]

        if not (self.limits[0] < value < self.limits[1]):
            self.num_failures += 1
            if self.num_failures == 1:
                _logger.error(f"Quantity '{name}' is {value}{units}. " +
                              f"This is outside limits ({self.limits[0]} to {self.limits[1]})")
                if self.action is not None:
                    _logger.warning("The above warning has triggered an action to correct it. " +
                                    "Hopefull the next log message will say what")
                    self.action()
            elif self._is_pow_two(self.num_failures):
                _logger.warning(f"Quantity '{name}' is {value}{units}. " +
                                f"This is still outside limits ({self.limits[0]} to {self.limits[1]}). " +
                                f"Has failed {self.num_failures} times")
        elif self.num_failures > 0:
            _logger.info(f"Quantity '{name}' is {value}{units}. " +
                         f"This is back in limits ({self.limits[0]} to {self.limits[1]})")
            self.num_failures = 0
