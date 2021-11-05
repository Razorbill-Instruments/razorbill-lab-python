# -*- coding: utf-8 -*-
"""
Tools for using a pc soundcard as a DAC
Only works on Windows.

Do not remote into a machine using this module. The sound will be redirected
to the remote machine, and will not play here.
"""
import winsound
import math
import array
import wave
from io import BytesIO
import numpy as np
from scipy.signal import tukey
import matplotlib.pyplot as plt

def play_waveform(waveform, sample_rate=48_000):
    """play a waveform as a mono sound. 
    
    `waveform` should be a list of ints in the signed 16 bit range.
    `sample_rate` is in Hz and should be a value supported by your soundcard
    
    Be careful if remoting in to the computer, the sound may be redirected to
    the client.    
    """
    data = array.array('h', waveform)
    stream = BytesIO()
    wav_file = wave.open(stream, 'w')
    wav_file.setparams((1, 2, sample_rate, len(data), "NONE", "Uncompressed"))
    wav_file.writeframes(data.tobytes())
    stream.seek(0)
    winsound.PlaySound(stream.read(), winsound.SND_MEMORY)
    
def plot_waveform(waveform, sample_rate=48_000):
    """ Plot a waveform using matplotlib. 
    
    Use to check waveforms before playing them. Same signature as play_waveform
    """    
    waveform = np.array(waveform)
    fig = plt.figure("instruments.sondcard.plot_waveform")
    fig.clear()
    ax = fig.add_subplot(111)
    t = np.arange(0, len(waveform)) * (1/sample_rate)
    ax.plot(t, waveform / (2**15-1))
    ax.plot([-0.1 * max(t), 1.1 * max(t)], [0, 0], color='grey')
    ax.set_xlabel('Time [s]')
    ax.set_ylabel('Amplitude [norm]')
    
def sine_wave(freq, cycles=100, volume=100, soften=0, sample_rate=48_000):
    """Return a sine waveform for use with play_waveform.
    
    If `soften` is not zero, that many cycles at each end will be softend with
    a tukey (cosine) window. For driving piezos, use 0.25 or more.
    """
    num_samples = int(sample_rate / freq * cycles)
    phase = np.linspace(0, 2 * math.pi * cycles, num_samples)
    wave = np.sin(phase) * (2 ** 15 - 1) * volume / 100
    if soften > 0:
        if soften > cycles // 2:
            raise(ValueError, "Cannot soften more than cycles/2 each end")
        window = tukey(num_samples, 2 * soften / cycles)
        wave *= window
    return wave.astype(int)

def sine_wave_duration(freq, duration=10, volume=100, soften=0, sample_rate=48_000):
    """Return a sine waveform for use with play_waveform.
    
    If `soften` is not zero, that many cycles at each end will be softend with
    a tukey (cosine) window. For driving piezos, use 0.25 or more.
    """
    cycles = int(freq * duration)
    return sine_wave(freq, cycles, volume, soften, sample_rate)