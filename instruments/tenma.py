#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Tenma products. Currently only supports DC power
supplies. Tenma are a Farnell own-brand, but I think these are the same as
Korad units.
"""

from . import Instrument


class DC_7227xx(Instrument):
    """Tenma 72-27xx Power supply.

    Developed with a 72-2705, probably suports most single channel supplies.
    """
    # TODO: use STATUS? command to get CV or CC, and OCP status from status byte

    _idnstring = 'TENMA 72-27'

    def _make_float_setter(command):
        return lambda self, value: self.raw_write(f"{command}:{value}\n")

    def _make_bool_setter(command):
        return lambda self, value: self.raw_write(f"{command}{int(value)}\n")

    def _make_float_getter(command):
        return lambda self: float(self.raw_query(f"{command}?\n"))

    current_limit = property(_make_float_getter('ISET1'), _make_float_setter('ISET1'))
    voltage_limit = property(_make_float_getter('VSET1'), _make_float_setter('VSET1'))
    current_actual = property(_make_float_getter('IOUT1?'))
    voltage_actual = property(_make_float_getter('VOUT1?'))
    output_enable = property(None, _make_bool_setter('OUT'))
    ocp_enable = property(None, _make_bool_setter('OCP'))
    keyboard_lock = property(None, _make_bool_setter('LOCK'))
