""" Module for measuring things, and writing the results to file.

Designed to work well with the instruments module. Normal usage is to create
a Quantity for everything you want to measure and then start a Recorder to
measure to file
"""

import logging
import sys
import numpy as np
import time
import __main__
try:
    import IPython
    have_ipython = True
except ModuleNotFoundError:
    have_ipython = False

_logger = logging.getLogger('measurement_system')
_environment_is_setup = False


def setup_environment():
    """
    Call this at the start of an experiment script/session to set up logging.

    Parameters
    ----------
    None.

    Returns
    -------
    None.

    """
    global _environment_is_setup
    if not _environment_is_setup:
        log_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(threadName)s > %(message)s',
            datefmt="%Y-%m-%d %H:%M:%S")
        root_logger = logging.getLogger('measurement_system')
        filename = "measurement log {}.log".format(time.strftime("%Y-%m-%d %H-%M-%S"))
        file_handler = logging.FileHandler(filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(log_formatter)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(log_formatter)
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers = [console_handler, file_handler]
        _logger.info("Measurement session being logged at {}".format(filename))

        def log_error(*args, **kwargs):
            _logger.critical('Unhandled error caused execution to terminate', exc_info=True)
        # This works in a basic python session, but not in ipython or spyder
        sys.excepthook = log_error
        # This is for ipython (which is also used by spyder)
        if have_ipython:
            IPython.core.interactiveshell.InteractiveShell.showtraceback = log_error

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

    def __init__(self, name, source, units, scalefactor=1, skiptest=False):
        self.name = name
        self.units = units
        self.scalefactor = scalefactor
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
            self.value

    @property
    def value(self):
        try:
            if type(self.name) is list:
                return list(np.multiply(self._get_value(), self.scalefactor))
            else:
                return self._get_value() * self.scalefactor
        except Exception as e:
            _logger.error("Error while evaluating measurement Quantity '{}':"
                          .format(self.name))
            _logger.error(str(e))
            raise e


def quantity_from_scanner(scanner, suffixes=[" Cap", " Loss"], units=["pF", "Gohm"],
                          scalefactor=[1e12, 1e-9], skiptest=False):
    """Build a Quantity from a CapScanner or similar object"""
    q_titles = []
    q_units = []
    q_scalefactor = []
    for channel in range(len(scanner)):
        q_units = q_units + units
        q_scalefactor = q_scalefactor + scalefactor
        cap = scanner.labels[channel]
        q_titles = q_titles + [cap + suffixes[0], cap + suffixes[1]]
    q = Quantity(q_titles, scanner.measure_all, q_units, q_scalefactor, skiptest)
    return q
