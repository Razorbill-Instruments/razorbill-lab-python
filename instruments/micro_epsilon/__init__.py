#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
micro_epsilon module. Provides classes for Micro Epsilon's various sensors
using their MEDAQLib DLL (written with 4.4.0.27352 but should be forward
compatible).
"""

from ctypes import WinDLL, sizeof, create_string_buffer, POINTER, byref
from ctypes import c_long, c_int, c_char_p, c_voidp, c_double
import os.path
from .. import _logger, instrument_registry

_module_path = os.path.dirname(os.path.abspath(__file__))

_error_codes = {
      0: 'ERR_NOERROR',
     -1: 'ERR_FUNCTION_NOT_SUPPORTED',
     -2: 'ERR_CANNOT_OPEN',
     -3: 'ERR_NOT_OPEN',
     -4: 'ERR_APPLYING_PARAMS',
     -5: 'ERR_SEND_CMD_TO_SENSOR',
     -6: 'ERR_CLEARUNG_BUFFER',
     -7: 'ERR_HW_COMMUNICATION',
     -8: 'ERR_TIMEOUT_READING_FROM_SENSOR',
     -9: 'ERR_READING_SENSOR_DATA',
    -10: 'ERR_INTERFACE_NOT_SUPPORTED',
    -11: 'ERR_ALREADY_OPEN',
    -12: 'ERR_CANNOT_CREATE_INTERFACE',
    -13: 'ERR_NO_SENSORDATA_AVAILABLE',
    -14: 'ERR_UNKNOWN_SENSOR_COMMAND',
    -15: 'ERR_UNKNOWN_SENSOR_ANSWER',
    -16: 'ERR_SENSOR_ANSWER_ERROR',
    -17: 'ERR_SENSOR_ANSWER_TOO_SHORT',
    -18: 'ERR_WRONG_PARAMETER',
    -19: 'ERR_NOMEMORY',
    -20: 'ERR_NO_ANSWER_RECEIVED',
    -21: 'ERR_SENSOR_ANSWER_DOES_NOT_MATCH_COMMAND',
    -22: 'ERR_BAUDRATE_TOO_LOW',
    -23: 'ERR_OVERFLOW',
    -24: 'ERR_INSTANCE_NOT_EXIST',
    -25: 'ERR_NOT_FOUND',
    -26: 'ERR_WARNING',
    -27: 'ERR_SENSOR_ANSWER_WARNING',
    }


class MEDAQlibError(Exception):
    """Exception raised if there is an error in the library"""
    pass


class MEDAQLib:
    """This class forms a fairly thin wrapper around the Micro Epsilon MEDAQLib
       library. For documentation of the methods, refer to the library docs.
    """
    def __init__(self):
        self._import_dll()
        self._configure_dll_types()
        buffer = create_string_buffer(20)
        self._dll.GetDLLVersion(buffer, 20)
        self.dll_version = buffer.value.decode('ascii')

    def _import_dll(self):
        python_is_64bit = sizeof(c_voidp) > 4
        if python_is_64bit:
            dllname = 'MEDAQLib64.dll'
        else:
            dllname = 'MEDAQLib32.dll'
        dll_path = os.path.join(_module_path, dllname)
        if os.path.exists(os.path.join(_module_path, dllname)):
            self._dll = WinDLL(dll_path)
        else:
            raise ImportError("Could not find MEDAQLib DLL")

    def _configure_dll_types(self):
        def check_error(error_code):
            if error_code == 0:
                return
            error_desc = _error_codes.get(error_code, "UNKOWN_ERROR")
            if error_code == -26:
                message = "Warning {} ({}) in MEDAQLib. This is usually a data buffer overflow."
                _logger.warn(message.format(error_code, error_desc))
                return
            if error_code == -27:
                message = "Warning {} ({}) in MEDAQLib. Received warning from hardware."
                _logger.warn(message.format(error_code, error_desc))
                return
            raise MEDAQlibError("Error {} ({}) in MEDAQLib".format(error_code, error_desc))

        def setup_types(func_name, argtypes):
            """Simplify wrapping ctypes functions using standard error codes"""
            func = self._dll.__getattr__(func_name)
            func.restype = check_error
            func.argtypes = argtypes

        self._dll.CreateSensorInstByNameU.argtypes = [c_char_p]
        setup_types('ReleaseSensorInstance', (c_long,))
        setup_types('SetParameterInt',       (c_long, c_char_p, c_int))
        setup_types('SetParameterDouble',    (c_long, c_char_p, c_double))
        setup_types('SetParameterString',    (c_long, c_char_p, c_char_p))
        setup_types('GetParameterInt',       (c_long, c_char_p, POINTER(c_int)))
        setup_types('GetParameterDouble',    (c_long, c_char_p, POINTER(c_double)))
        setup_types('GetParameterString',    (c_long, c_char_p, c_char_p, POINTER(c_long)))
        setup_types('ClearAllParameters',    (c_long,))
        setup_types('OpenSensor',            (c_long,))
        setup_types('CloseSensor',           (c_long,))
        setup_types('SensorCommand',         (c_long,))
        setup_types('DataAvail',             (c_long, POINTER(c_int)))
        setup_types('TransferData',          [c_long, POINTER(c_int), POINTER(c_double), c_int, POINTER(c_int)])
        setup_types('Poll',                  [c_long, POINTER(c_int), POINTER(c_double), c_int])
        setup_types('GetError',              (c_long, c_char_p, c_int))
        setup_types('GetDLLVersion',         (c_char_p, c_long))

    def create_sensor(self, name):
        handle = self._dll.CreateSensorInstByName(name.encode('ascii'))
        if handle == 0:
            raise MEDAQlibError("MEDAQLib failed to create sensor")
        return handle

    def release_sensor(self, handle):
        self._dll.ReleaseSensorInstance(handle)

    def set_parameter_int(self, handle, parameter, value):
        self._dll.SetParameterInt(handle, parameter.encode('ascii'), int(value))

    def set_parameter_double(self, handle, parameter, value):
        self._dll.SetParameterDouble(handle, parameter.encode('ascii'), float(value))

    def set_parameter_string(self, handle, parameter, value):
        self._dll.SetParameterString(handle, parameter.encode('ascii'), value.encode('ascii'))

    def get_parameter_int(self, handle, parameter):
        value = c_int()
        self._dll.GetParameterInt(handle, parameter.encode('ascii'), byref(value))
        return value.value

    def get_parameter_double(self, handle, parameter):
        value = c_double()
        self._dll.GetParameterDouble(handle, parameter.encode('ascii'), byref(value))
        return value.value

    def get_parameter_string(self, handle, parameter):
        value = create_string_buffer(100)
        self._dll.GetParameterString(handle, parameter.encode('ascii'), value, byref(c_int(100)))
        return value.value.decode('ascii')

    def clear_parameters(self, handle):
        self._dll.ClearAllParameters(handle)

    def open_sensor(self, handle):
        self._dll.OpenSensor(handle)

    def close_sensor(self, handle):
        self._dll.CloseSensor(handle)

    def sensor_command(self, handle):
        self._dll.SensorCommand(handle)

    def data_available(self, handle):
        num_points = c_int()
        self._dll.DataAvail(handle, byref(num_points))
        return num_points.value

    def data_transfer(self, handle, num_points):
        array_type = c_double * num_points
        self._dll.TransferData.argtypes[2] = POINTER(array_type)
        pointer_data = array_type()
        num_read = c_int()
        self._dll.TransferData(handle, None, pointer_data, num_points, byref(num_read))
        data = [pointer_data[i] for i in range(len(pointer_data))]
        if num_read.value < num_points:
            _logger.warning("Asked for more data than there was in the MEDAQLib buffer")
            data = data[0:num_read.value]
        return data

    def flush_buffer(self, handle):
        num_read = c_int()
        self._dll.TransferData(handle, None, None, 0, byref(num_read))

    def poll(self, handle, num_points):
        array_type = c_double * num_points
        self._dll.Poll.argtypes[2] = POINTER(array_type)
        pointer_data = array_type()
        self._dll.Poll(handle, None, pointer_data, num_points)
        data = [pointer_data[i] for i in range(len(pointer_data))]
        return data

    def get_error_text(self, handle):
        value = create_string_buffer(200)
        self._dll.GetError(handle, value, c_int(100))
        return value.value.decode('ascii')


class _Multiton(type):
    """ Metaclass for creating multitions. A new object will only be created
    if there is not another object of the class with the same name and  address
    in the instrument_registry. Not a VISA instrument so makes up a fake VISA
    name, otherwise the same as the version at instruments._Multition
    """
    def __call__(cls, address, *args, **kwargs):
        visa_name = "uE_device_at_" + address
        if visa_name not in instrument_registry:
            self = cls.__new__(cls, *args, **kwargs)
            cls.__init__(self, address, *args, **kwargs)
            instrument_registry[visa_name] = self
        else:
            _logger.info("Reusing existing " + str(instrument_registry[visa_name]))
        return instrument_registry[visa_name]


class _Sensor(metaclass=_Multiton):
    """This is a base class for all micro epsilon sensor. Subclass it"""
    def __str__(self):
        return type(self).__name__ + ' instrument at ' + self.address

    def __init__(self, address):
        self._lib = MEDAQLib()
        self.address = address
        self._handle = None
        self._frame_size = None
        self._handle = self._lib.create_sensor(self._name)
        self._lib.set_parameter_string(self._handle, "IP_RemoteAddr", address)
        self._lib.set_parameter_string(self._handle, "IP_Interface", "TCP/IP")
        self._lib.open_sensor(self._handle)
        _logger.info("Connected to " + str(self))

    def __del__(self):
        if self._handle is not None:
            try:
                self._lib.close_sensor(self._handle)
            finally:
                self._lib.release_sensor(self._handle)
        _logger.info("Disconnected from " + str(self))


class _Channel():
    """This is a base class for individual channels on a sensor. Subclass it"""
    def __init__(self, lib, num, num_channels, parent_handle):
        super().__init__()
        self._lib = lib
        self._num = num
        self._num_channels = num_channels
        self._parent_handle = parent_handle

    def _poll(self):
        values = self._lib.poll(self._parent_handle, self._num_channels)
        if self._num == 0:
            return values
        else:
            return values[self._num-1]

    measure = property(fget=_poll, doc="The most recent measured position(s)")
