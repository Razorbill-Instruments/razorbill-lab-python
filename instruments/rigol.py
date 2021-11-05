#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for interfacing with Rigol Instruments
"""

from . import ScpiInstrument, ChildInstrument, _scpi_property, _logger
import matplotlib.pyplot as plt
import time

class _Ds1000_Channel(ChildInstrument):
    """Input channel on a DS1000 series scope"""
    enable = _scpi_property(':CHAN{subaddr:}:DISP', '{:bool}')
    vert_offset = _scpi_property(':CHAN{subaddr:}:OFFS', '{:g}')
    vert_scale = _scpi_property(':CHAN{subaddr:}:SCAL', '{:g}')
    vert_vernier = _scpi_property(':CHAN{subaddr:}:VERN', '{:bool}')

class Ds1000(ScpiInstrument):
    """DS1054 and related scopes"""
    def _setup(self):
        self.channels = {1: _Ds1000_Channel(self, 1), 
                         2: _Ds1000_Channel(self, 2),
                         3: _Ds1000_Channel(self, 3),
                         4: _Ds1000_Channel(self, 4)}
    
    _idnstring = 'RIGOL TECHNOLOGIES,DS1'
    
    samp_rate = _scpi_property('ACQ:SRAT', '{:g}', can_set=False)
    memory_depth = _scpi_property('ACQ:MDEP', '{:g}', can_set=False)
    horiz_posn = _scpi_property(':TIM:OFFS', '{:g}', doc="Horisontal position in sec. Positive moves trigger point left.")
    horiz_scale = _scpi_property(':TIM:SCAL', '{:g}', doc="Horisontal scale, in sec/div. Rounds up.")
    trig_edge_level = _scpi_property(':TRIG:EDGE:LEV', '{:g}')
    waveform_xincrement = _scpi_property(':WAV:XINC', '{:g}', can_set=False)
    
    
    
    
    def run(self):
        """Start acquring, same as run button the the front"""
        self.raw_write(':RUN')
        
    def single(self):
        """Start acquring, same as single button the the front"""
        self.raw_write(':SING')
    
    def stop(self):
        """Stop the scope, use after a run() command"""
        self.raw_write(':STOP')
        
    def _read_waveform_chunk(self, start, stop):
        time.sleep(0.01)
        self.raw_write(f':WAV:STAR {start}')
        self.raw_write(f':WAV:STOP {stop}')
        time.sleep(0.01)
        self.raw_write(':WAV:DATA?')
        time.sleep(0.05)
        resp = self.raw_read()
        data_string = resp[11:] # strip header
        return [float(i) for i in data_string.split(',')]
        
    def _read_waveform(self, channel, depth=None, chunk_size=100_000):
        # chunk size > 589792 casues empty response. Chunks size > 100k sometimes odd?
        _logger.info(f"Reading channel {channel} waveform from scope.")
        for attempt in range(3):
            failed = False
            try:
                with self.lock:
                    self.stop()
                    self.raw_write(f':WAV:SOUR CHAN{channel}')
                    self.raw_write(':WAV:MODE RAW')
                    self.raw_write(':WAV:FORM ASC')
                    time.sleep(0.2)
                    if depth == None:
                        depth = self.memory_depth
                    depth = int(depth)
                    num_batches = depth // chunk_size
                    data = []
                    for batch in range(num_batches):
                        start = batch * chunk_size + 1
                        end = batch * chunk_size + chunk_size
                        _logger.debug(f'reading channel {channel}: batch {batch + 1} / {num_batches} points {start}:{end}')
                        data += self._read_waveform_chunk(start, end)
                        time.sleep(0.2)
                    if depth % chunk_size:
                        _logger.debug(f'reading channel {channel}: tail')
                        data += self._read_waveform_chunk(num_batches * chunk_size + 1, depth)
                        time.sleep(0.2)
                    return data
            except Exception as e:
                failed = True
                if attempt < 2:
                    _logger.warning(f"Failed to read from scope, trying again: {e}")
                else:
                    _logger.error(f"Failed to read from scope, giving up: {e}")
                    raise(e)
            if not failed:
                break
            
    def read_waveforms(self, channels=[1,2,3,4], depth=None, plot=False):
        """Read waveforms from scope.
        
        Scope must have been triggered and be displaying a waveform. Returns an
        numpy.array where hte forst column is time and the other columns are the
        voltages of the channels in the channel list. Id depth is not None,
        only the first that many points are read.
        """
        with self.lock:
            xinc = self.waveform_xincrement
            data = [None]
            for ch in channels:
                data.append(self._read_waveform(ch, depth))
            x = list(range(len(data[1])))
            data[0] = [i * xinc for i in x]
            if plot:
                fig = plt.figure('Scope Read')
                fig.clear()
                ax = fig.add_subplot(111)
                for ix,ch in enumerate(channels):
                    ax.plot(data[0], data[ch+1], label=f'Channel {ch}')
                ax.set_xlabel('Time [s]')
                ax.set_ylabel('Voltage [V]')
            return data
                