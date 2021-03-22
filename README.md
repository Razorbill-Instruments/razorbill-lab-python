# razorbill-lab-python
This library is a collection of modules we use in the Razorbill Instruments labs for QA and R&D. It is designed as a small, simple, easy to extend interface for various scientific instruments. It also includes features for gathering data and (through KST) plotting it in real time and some functionality designed to make experiment scripts easy to write. We have decided to make it publically available as people often ask about it, but it is not a product or part of any of our products, and doesn't come with any support. It is made available under the MIT licence - see the LICENCE file for details.

I started writing this quite a few years ago, and since then, several other similar projects have appeared, and many are now much more feature-rich. These include QCoDeS, PyMeasure easy-scpi and probably others. Consider checking those out too.

## Features
* Most SCPI-like instruments can be supported by writing simple python classes - most SCPI commands only need one line of python code.
* Support for instuments with several similar channels, such as DC power supplies or temperature monitors.
* Some instruments already have classes.
* Instrument access is thread safe
  * Attempting to connect to an existing instrument returns the same object
  * Instrument objects have locks, which ensure each thread gets the response to its own query, not queries from other threads.
* `Quantity`s associate basic metadata with measurements
* `Recorders` and `AutoRecorders` can log Quantities on demand or automatically in the background
* Includes `Wait`s, which allow an experiment to wait until a Quantity meets certain requirements before proceeding - for example to wait for a cryostat to stabilise at a set temperature before taking measurements.
* Includes `Sequences`, which is a way of running an experiment script in its own pauseable thread, so other commands can run at the console.
* Key actions and progress through an experiement are logged to file and to the console with timestamps.


# Getting started
## Dependencies
The library was developed on Windows 10. It does use Windows APIs for pop-up message boxes in `measurement.wait.For_Click`, but could probably be converted to other platforms without much difficulty (or just delete the offending class).

You will need the following dependencies:
* Python Modules (all available through pip)
  * numpy
  * scipy (optional, used by some instruments for interpolation)
  * pyvisa
  * parse
* Other libraries
  * A VISA implementation. VISA is a standard API for working with instruments, and many instrument manufacturers have their own implementations of it. They have different licencing rules, some are only free if you own hardware from that vendor. We use [NI-VISA](https://www.ni.com/en-gb/support/downloads/drivers/download.ni-visa.html) and have also tested with [R&S VISA](https://www.rohde-schwarz.com/uk/applications/r-s-visa-application-note_56280-148812.html), but any VISA should work. 
  * [KST](https://kst-plot.kde.org/) (optional, for realtime plotting)
  * Micro Epsilon MEDAQLib (optional, for connecting to their instruments)

We use [Spyder](www.spyder-ide.org) to write scripts and run experiments and it works well, but this library shouldn't depend on Spyder in any way.

## Setup
Before using this library you will need to:
* Add the modules to your PYTHONPATH or otherwise make sure they can be imported
* Configure the path to the KST executable in measurement.recorders if you want realtime plotting.
* If you are using Spyder, disable Spyder's User Module Reloader for the instruments module.

## Basic use
Provided there is a class for the instrument you are using, you can connect to the instrument and use it like this:
```python
from measurement import setup_environment
from instruments.keysight import E4980A
setup_environment()        # set up logging etc.
meter = E4980A('SOME::VISA::ADDRESS') # connect
meter.freq = 100000        # set measurement frequency to 100k
meter.mode = "CPRP"        # set measurement mode to Cp-Rp
capacitance = meter.meas   # take a measurement
```
You can then define a `Quantity`. A `Quantity` defines something you want to control or measure, and usually combines a property like `meter.meas` with a description and unit. Then, you can create a `Recorder` which will measure several quantities and write the results to a CSV file. The description and unit go into the file as headers.
```python
from measurement import Quantity
from measurement.recorders import Recorder
cap = Quantity(['Capacitance', 'loss'], (bridge, 'meas'), ['pF','GOhm'])
rec = Recorder('filename', [cap], plot_kst=True)
rec.record_line()
# do something
rec.record_line()
rec.stop()
```
For more detailed usage, refer to the docstrings within the library modules.


# Improving the library

## Adding more instruments
The library designed to be easy to add instruments too, especially if the instruments support SCPI-like commands.  In many cases, you will just need to subclass `ScpiInstrument`, set an `_idnstring` and then add parameters using `_scpi_property()`. The `instruments.keysight.E4980A` class used in the examples above is a good example of a simple instrument you can use as a template. It also includes some functions which don't use `_scpi_property()`, this is appropriate for things which aren't really properties of the instrument.

Many of the supported instruments are incomplete. Adding more properties with `_scpi_property()` may add more functionality.

## Bugs and Feature Requests
If you find a bug, please go ahead and open an issue, but bear in mind that it it does not affect us in our lab, we may not find the time to fix it anytime soon if at all. The same goes for feature requests, though they are less likley to make it to the top of our todo lists. But you never know!


## Contributing
Posting code snippets in bug reports or opening pull requests are both reasonable ways to suggest changes.

Style is generally PEP8, up to 120 characters wide, numpy style docstrings. But this is not totally consistent within the library and certainly isn't a requirement for accepting contributions.

The library is currently Copyright Razorbill Instruments, and licenced under the MIT licence. We don't forsee this changing, but would like to maintain the ability to relicence it or use it ourselves without the MIT licence in the future, and we don't want to have to disentangle code with different copyright status. For this reason, we ask contributors to assign copyright for their contributions to us.  If the library ever reaches the point where it contains significant quantities of code not written by us, we will revisit this.

# Disclaimer
This library works for us, but we offer no warranties whatsoever.  It may fail to gather data when you want it, it may delete data you already gathered, it may crash your PC, it may brick your instruments, it may summon an eldritch abomination from beyond the bounds of time and space to devour your lab. Only the first one has ever happened to us, but we still won't take responsibility for any consequences of using this library. Use it entirely at your own risk. We might provide help and advice but we are not obliged to. See also the LICENCE file for the legalese version. 

Note this disclaimer applies even if you have bought one of our products and are trying to use the library with it. Our products are provided with drivers and an example gui (available on our website) and this library is provided separately, for free, to anyone, without support or warranty.
