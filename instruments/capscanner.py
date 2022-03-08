#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Scanner based on a bridge and several multiplexers, plus helper classes.
Normal use is to construct a CapSet for each multiplexer then a CapScanner
using them.  Multiple CapScanners using the same bridge are supported but
the necessary locking is not well tested.
"""
import time
import random
from instruments import _logger


class CapSet:
    def __init__(self, mplex, labels):
        """
        A set of labels for the channels on a multiplexer.

        Parameters
        ----------
        mplex : instruments.razorbill.MP240
            The instument object for the multiplexer.
        labels : tuple
            Four labels for the four channels. Use None if not connected

        Returns
        -------
        None.

        e.g. mp1 = CapSet(MP240('COM1'), ('cap1', 'cap2', None, None))

        """
        self.mplex = mplex
        self.labels = labels
        self.caps = *(label for label in self.labels if label is not None),

    def __len__(self):
        return sum(label is not None for label in self.labels)

    def mp_position(self, output):
        """converts from index of populated channels to index of all channels"""
        not_nones = [i for i, l in enumerate(self.labels) if l is not None]
        return not_nones[output - 1] + 1


class CapScanner:
    def __init__(self, bridge, capsets):
        """
        Scanner which combines bridge and multiplexers into one instrument

        Parameters
        ----------
        bridge : instruments.keysight.E4980
            The capacitance bridge used to make measurements
        capsets : tuple of CapSets
            One CapSet per multiplexer connected to the bridge

        Returns
        -------
        None.

        Construct using the bridge and CapSets, then call select to set a
        particular channel onto the bridge (one multiplexer will be set to
        the correct channel, all others to channel 0). Call measure to select
        a channel then make a measurement.

        It is possible to have more than one CapScanner with the same bridge
        and different, overlapping, or identical CapSets.  In this case
        they can set conflicting select routes, but if measure is called
        the correct route will be kept until the measurement is complete.

        If there are multiplexers connected but unused, it would be prudent to
        pass them in with a CapSet(mp, (None)) so they will be turned off as
        necessary.

        See also: measurement.quantity_from_scanner

        """
        self.bridge = bridge
        self.capsets = capsets
        self._bridge_wait_time = 0  # For small capacitances, first measurement after abort is fine.
        self._relay_wait_time = 0.01  # probably conservative, in testing even 0 was fine.
        self._all_locks = [bridge.lock] + [capset.mplex.lock for capset in capsets]
        self._have_locks = [False] * len(self._all_locks)
        self.labels = sum((capset.caps for capset in capsets), ())

    def __len__(self):
        return sum([len(i) for i in self.capsets])

    def _aquire_locks(self):
        while not all(self._have_locks):
            for ix, lock in enumerate(self._all_locks):
                self._have_locks[ix] = lock.acquire(timeout=0.1)
                if not self._have_locks[ix]:
                    break
            if not all(self._have_locks):
                self._release_locks
                wait = 0.5 + random.random()
                _logger.warning(
                    f"CapScanner could not lock all instruments. Trying again in {wait:.2f}s")
                time.sleep(wait)

    def _release_locks(self):
        for ix, lock in enumerate(self._all_locks):
            if self._have_locks[ix]:
                lock.release()
                self._have_locks[ix] = False

    def __del__(self):
        try:
            self._release_locks()
        except Exception:
            pass

    def select(self, channel):
        """Set a single channel through the multiplexers to the bridge"""
        if channel > len(self):
            raise RuntimeError(f"This CapScanner only has {len(self)} channels but channel {channel} was requested")
        count = 0
        for capset in self.capsets:
            low = count + 1
            high = count + len(capset)
            count = high
            if low <= channel <= high:
                capset.mplex.output = capset.mp_position(channel - low + 1)
            else:
                capset.mplex.output = 0
        time.sleep(self._relay_wait_time)
        self.bridge.abort_meas()  # restart measurment

    def measure(self, channel):
        """Measure a capactior. Configures multiplexers and makes measurement"""
        try:
            self._aquire_locks()
            self.select(channel)
            time.sleep(self._bridge_wait_time)
            return self.bridge.meas_all
        finally:
            self._release_locks()

    def measure_all(self):
        """Measures all the attached capacitors and returns a list of values"""
        values = []
        for channel in range(len(self)):
            values = values + self.measure(channel + 1)
        return values


class AutoCapScanner(CapScanner):
    # TODO: write this if we need it.
    # Auto version needs it's own thread. Main advantage is that it is IO bound and
    # won't have to wait for other IO. Maybe a multi-thread Recorder would be better?
    # It keeps changing round the caps, measuring them as fast as possible.

    # It has a get immediate option to get the most recent buffered data
    # it has a blocking option which makes all new measurements
    # it could also have an option which guaranttees new data, and waits if necessary
    # though it won't be able to identify different consumers so "new" is relative
    # One of the latter two would be best for rate limiting a recorder
    # What if I have different consumers with different channels?
    # Would I support different rates in that case?
    # Does this need to monopolise the bridge (multition? keep hold of lock?)
    pass


if __name__ == "__main__":
    from threading import RLock
    from measurement import quantity_from_scanner

    print("Testing CapScanner Module")

    class DummyInstr:
        def __init__(self, name):
            self.visa_name = name
            self.lock = RLock()

        def set_output(self, output):
            print(f"mplex at {self.visa_name} set to {output}")

        def meas(self):
            print(f"bridge at {self.visa_name} made measurement")
            return [1, 2]

        output = property(fget=None, fset=set_output)
        meas = property(fget=meas, fset=None)

    m1 = DummyInstr('no1')
    m2 = DummyInstr('no2')
    m3 = DummyInstr('no3')
    m4 = DummyInstr('no4')
    c1 = CapSet(m1, ('cap1', 'cap2', 'cap3', 'cap4'))
    c2 = CapSet(m2, ('cap5', 'cap6', None, None))
    c3 = CapSet(m3, (None, None, None))
    c4 = CapSet(m4, ('cap7', None, 'cap8', None))
    assert(len(c1) == 4)
    assert(len(c2) == 2)
    assert(len(c4) == 2)
    print(str(c1))
    print(str(c3))
    scan = CapScanner(DummyInstr('bridge'), (c1, c2, c3, c4))
    assert(len(scan) == len(c1) + len(c2) + len(c3) + len(c4))
    quantity_from_scanner(scan)
