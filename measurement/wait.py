#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Various functions for waiting for some condition to be true before continuing
the experiment.  If the calling code is running in a measurment.Sequence it
can be paused or aborted during one of these `Wait`s.
"""

import time
from datetime import datetime
import numpy
from . import _logger as _measlogger
import threading
import ctypes
from measurement.sequences import Sequence
from measurement import ThreadWithExcLog

_logger = _measlogger.getChild('wait')


class _Wait():
    """ This is a superclass for the other Wait classes. """

    def __init__(self, period, timeout):
        self.start_time = time.time()
        self.period = period
        self.timeout = timeout
        self.sequence = None
        self._done = False
        if isinstance(threading.current_thread(), Sequence):
            self.sequence = threading.current_thread()

    def run(self):
        paused = False
        has_timed_out = False
        skip = False
        while paused or not any([self._done, has_timed_out, skip]):
            time.sleep(self.period)
            if self.sequence is not None:
                self.sequence._check_stop()
                paused = self.sequence._check_pause()
                if self.sequence._skip_requested:
                    skip = True
                    self.sequence._skip_requested = False
                    _logger.warning(f'{self} is ending early due to external override')
            self._done = self.test()
            if (time.time() - self.start_time) > self.timeout:
                _logger.warning(f"{self} is ending due to timeout")
                has_timed_out = True

    def __str__(self):
        start = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
        return f"wait.{self.__class__.__name__} started at {start}"


class In_Band(_Wait):
    def __init__(self, quantity, low, high, target_time, period=1,
                 quantity_index=0, timeout=numpy.inf):
        """
        Blocks until `quantity` is between `high` and `low` for `target_time`

        This is used to delay an experiment until some measurement quantity
        is in a certain band. For example, to wait until a cryostat settles
        at a target tempearture.

        Construction
        ------------
        quantity : a measurement.Quantity
            The wait will end or not depending on the value of this quantity

        low : number
            minimum value of quantity

        high : number
            maximum value of quantity

        target_time : number
            contiguous time quantity must be in band, in seconds

        period : number
            how often to check the Quantity, in seconds (default is 1)

        quantity_index : integer
            If quantity is a list Quantity, watch this item

        timeout : integer
            If set, the function will timeout if it is still not in band after
            this many seconds
        """
        super().__init__(period, timeout)
        _logger.info(f"Waiting for {quantity.name} to be in [{low}, {high}] for {target_time}s...")
        self.target_count = target_time / period
        self.stable_count = 0
        self.quantity = quantity
        self.quantity_index = quantity_index
        self.low = low
        self.high = high
        self.run()
        _logger.info(f"Done waiting for {quantity.name}")

    def test(self):
        if type(self.quantity.name) is list:
            meas = self.quantity.value[self.quantity_index]
        else:
            meas = self.quantity.value
        if meas > self.low and meas < self.high:
            self.stable_count += 1
        else:
            self.stable_count = 0
        return self.stable_count > self.target_count


class Is_Equal(_Wait):
    def __init__(self, quantity, target, target_time, period=1,
                 quantity_index=0, timeout=numpy.inf):
        """
        Blocks until `quantity` is equal to target for `target_time`

        This is used to delay an experiment until some measurement quantity
        is a certain value. For example, for a state flag to change.  For
        continuous variables use In_Band instead.

        Construction
        ------------
        quantity : a measurement.Quantity
            The wait will end or not depending on the value of this quantity

        target : number
            the target for the quantity to reach. Can be an IntEnum.

        target_time : number
            contiguous time quantity must be in band, in seconds

        period : number
            how often to check the Quantity, in seconds (default is 1)

        quantity_index : integer
            If quantity is a list Quantity, watch this item

        timeout : integer
            If set, the function will timeout if it is still not in band after
            this many seconds
        """
        super().__init__(period, timeout)
        _logger.info(f"Waiting for {quantity.name} to be {target} for {target_time}s...")
        self.target_count = target_time / period
        self.stable_count = 0
        self.quantity = quantity
        self.quantity_index = quantity_index
        self.target = target
        self.run()
        _logger.info(f"Done waiting for {quantity.name}")

    def test(self):
        if type(self.quantity.name) is list:
            meas = self.quantity.value[self.quantity_index]
        else:
            meas = self.quantity.value
        if meas == self.target:
            self.stable_count += 1
        else:
            self.stable_count = 0
        return self.stable_count > self.target_count


class Is_Stable(_Wait):
    def __init__(self, quantity, variation, test_time, period=1,
                 quantity_index=0, timeout=numpy.inf):
        """Blocks until `quantity` is has an rms deviation < `variation`

        This is used to delay an experiment until some measurement quantity
        stops changing. For example until a cryostat has reached base
        temperature, but that temperature is not known in advance.

        quantity : measurement.Quantity
            The wait will end or not depending on the value of this quantity

        variation : number
            Permissable rms, as a fraction of the measured value

        test_time : number
            time over which rms is measured, in seconds

        period : number
            how often to check the Quantity, in seconds (default 1)

        quantity_index : integer
            Where quantity is a list Quantity, watch this item

        timeout: integer
            If set, the function will timeout if it is still not stable after
            this many seconds
        """
        super().__init__(period, timeout)
        _logger.info(f"Waiting for {quantity.name} to be stable to {variation} for {test_time}s...")
        self.num_values = int(test_time / period)
        self.quantity = quantity
        self.variation = variation
        self.data = numpy.ones(self.num_values) * numpy.nan
        self.pointer = 0
        self.run()
        _logger.info(f"Done waiting for {quantity.name}")

    def test(self):
        if type(self.quantity.name) is list:
            meas = self.quantity.value[self.quantity_index]
        else:
            meas = self.quantity.value
        self.data[self.pointer] = meas
        self.pointer = (self.pointer + 1) % self.num_values
        mean = numpy.mean(self.data)
        rms_dev = numpy.sqrt(numpy.mean(numpy.square(self.data - mean)))
        metric = rms_dev / numpy.abs(mean)
        return metric < self.variation


class For_Seconds(_Wait):
    def __init__(self, number):
        """Blocks for a fixed time, in seconds. Use instead of time.sleep."""
        super().__init__(1, numpy.inf)
        self.number = number
        if number > 60:
            _logger.info(f"Waiting for {number} seconds...")
        self.run()
        if number > 60:
            _logger.info("...done waiting")

    def test(self):
        return (time.time() - self.start_time) > self.number


class For_Click(_Wait):
    def __init__(self, msg='', title="Script Waiting", period=1, timeout=numpy.inf):
        """Pops up a message box and waits until it is dismissed."""
        super().__init__(period, timeout)
        thread_name = threading.current_thread().name
        msg = msg + f"\n\nThread '{thread_name}' is paused.\n"
        msg = msg + "Press 'OK' to continue."
        _logger.debug("Waiting for message box click...")

        def thread_target():
            resp = 0
            while resp != 1:
                resp = ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10141)

        self.popup_thread = ThreadWithExcLog(target=thread_target, name="Wait For Click")
        self.popup_thread.start()
        self.run()
        _logger.debug("...done waiting")

    def test(self):
        return not self.popup_thread.is_alive()


def in_band(quantity, low, high, target_time, period=1, quantity_index=0, timeout=numpy.inf):
    _logger.warning("function in_band is depreciated. Use class In_Band instead")
    In_Band(quantity, low, high, target_time, period, quantity_index, timeout)


def is_stable(quantity, variation, test_time, period=1, quantity_index=0, timeout=numpy.inf):
    _logger.warning("function is_stable is depreciated. Use class Is_Stable instead")
    Is_Stable(quantity, variation, test_time, period, quantity_index, timeout)
