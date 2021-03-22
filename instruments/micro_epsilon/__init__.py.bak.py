# -*- coding: utf-8 -*-
"""
micro_epsilon module. Provides classes for Micro Epsilon's various sensors
using their MEDAQLib DLL (written with 4.4.0.27352 but should be forward
compatible).
"""

from ctypes import WinDLL, sizeof, create_unicode_buffer, create_string_buffer, POINTER
from ctypes import c_long, c_int, c_char_p, c_voidp, c_double
import os.path
from abc import ABC

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
        self._buffer = create_unicode_buffer(20)
        errcode = self._dll.GetDLLVersionU(self._buffer, 20)
        self._check_error(errcode)
        self.dll_version = self._buffer.value
        
        self._dll.CreateSensorInstByNameU.argtypes = [c_char_p]
        self._dll.ReleaseSensorInstance.argtypes = [c_long]
        self._dll.ReleaseSensorInstance.restype = self._check_error
#        self._dll.OpenSensorTCPIP.argtypes = [c_long, c_char_p]
#        self._dll.OpenSensorTCPIP.restype = self._check_error
        self._dll.CloseSensor.argtypes = [c_long]
        self._dll.CloseSensor.restype = self._check_error
        
#        self._dll.ExecSCmd.argtypes =          [c_long, c_char_p]
#        self._dll.SetIntExecSCmd.argtypes =    [c_long, c_char_p, c_char_p, c_int]
#        self._dll.SetDoubleExecSCmd.argtypes = [c_long, c_char_p, c_char_p, c_double]
#        self._dll.SetStringExecSCmd.argtypes = [c_long, c_char_p, c_char_p, c_char_p]
#        self._dll.ExecSCmdGetInt.argtypes =    [c_long, c_char_p, c_char_p, POINTER(c_int)]
#        self._dll.ExecSCmdGetDouble.argtypes = [c_long, c_char_p, c_char_p, POINTER(c_double)]
#        self._dll.ExecSCmdGetString.argtypes = [c_long, c_char_p, c_char_p, c_char_p, POINTER(c_long)]
#        self._dll.ExecSCmd.restype = self._check_error
#        self._dll.SetIntExecSCmd.restype = self._check_error
#        self._dll.SetDoubleExecSCmd.restype = self._check_error
#        self._dll.SetStringExecSCmd.restype = self._check_error
#        self._dll.ExecSCmdGetInt.restype = self._check_error
#        self._dll.ExecSCmdGetDouble.restype = self._check_error
#        self._dll.ExecSCmdGetString.restype = self._check_error
        
        self._dll.DataAvail.argtypes = [c_long, c_int]
        self._dll.DataAvail.restype = self._check_error
        self._dll.TransferData.argtypes = [c_long, POINTER(c_int), POINTER(c_double), c_int, POINTER(c_int)]
        self._dll.TransferData.restype = self._check_error
        self._dll.Poll.argtypes = [c_long, POINTER(c_int), POINTER(c_double), c_int]
        self._dll.Poll.restype = self._check_error
        
        
    def _check_error(self, error_code):
        if error_code == 0:
            return
        error_desc = _error_codes.get(error_code, "UNKOWN_ERROR")
        raise MEDAQlibError("Error {} ({}) in MEDAQLib".format(error_code, error_desc))

    def create_sensor(self, name):
        handle = self._dll.CreateSensorInstByName(name.encode('ascii'))
        if handle == 0:
            raise MEDAQlibError("MEDAQLib failed to create sensor")
        return handle
    
    def release_sensor(self, handle):
        self._dll.ReleaseSensorInstance(handle)
        
#    def open_sensor_tcpip(self, handle, address):
#        self._dll.OpenSensorTCPIP(handle, address.encode('ascii'))
        
    def close_sensor(self, handle):
        self._dll.CloseSensor(handle)
    
#    def exec_cmd(self, handle, command):
#        self._dll.ExecSCmd(handle, command.encode('ascii'))
#    
#    def exec_cmd_set_int(self, handle, command, parameter, value):
#        self._dll.SetIntExecSCmd(handle, command.encode('ascii'), parameter.encode('ascii'), value)
#        
#    def exec_cmd_set_double(self, handle, command, parameter, value):
#        self._dll.SetDoubleExecSCmd(handle, command.encode('ascii'), parameter.encode('ascii'), value)
#    
#    def exec_cmd_set_string(self, handle, command, parameter, value):
#        self._dll.SetStringExecSCmd(handle, command.encode('ascii'), parameter.encode('ascii'), value.encode('ascii'))
#    
#    def exec_cmd_get_int(self, handle, command, parameter):
#        pointer = POINTER(c_int)
#        self._dll.ExecSCmdGetInt(handle, command.encode('ascii'), parameter.encode('ascii'), pointer)
#        return pointer.contents
#    
#    def exec_cmd_get_double(self, handle, command, parameter):
#        pointer = POINTER(c_double)
#        self._dll.ExecSCmdGetDouble(handle, command.encode('ascii'), parameter.encode('ascii'), pointer)
#        return pointer.contents
#    
#    def exec_cmd_get_string(self, handle, command, parameter):
#        buffer = create_string_buffer(100)
#        self._dll.ExecSCmdGetString(handle, command.encode('ascii'), parameter.encode('ascii'), buffer, 100)
#        return buffer.value
    
    def data_available(self, handle):
        pointer = POINTER(c_int)
        self._dll.DataAvail(handle, pointer)
        return pointer.contents
    
    def data_transfer(self, handle, num_points):
        pointer_data = POINTER(c_int*num_points)
        pointer_num = POINTER(c_int)
        self._dll.TransferData(handle, pointer_data, None, num_points, pointer_num)
        data = pointer_data.contents
        if pointer_num.contents < num_points:
            print("WARNING: Asked for more data than there was in the MEDAQLib buffer")
            data = data[0:pointer_num.contents-1]
        return data

    def poll(self, handle, num_points):
        pointer_data = POINTER(c_int*num_points)
        self._dll.Poll(handle, pointer_data, None, num_points)
        data = pointer_data.contents
        return data
        
    #TODO: consider logging
    
class _Controller(ABC):
    def __init__(self, name, address):
        self._lib = MEDAQLib()
        self.address = address
        self._name = name
        self._handle = None
    
    def __enter__(self):
        self._handle = self.lib.create_sensor(self._name)
        self._lib.open_sensor_tcpip(self._address)
    
    def __exit__(self):
        if self._handle is not None:
            try:
                self._lib.close_sensor(self._handle)
            finally:
                self._lib.release_sensor(self._handle)