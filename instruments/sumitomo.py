#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#
"""
Module for controlling Sumitomo Compressors and cold heads
"""
from . import Instrument
    
class F70(Instrument):
    """ 
    Sumitomo F70 Helium compressor with Gifford-McMahon cold head 
    =============================================================
        
    Module for controling and monitoring the compressor and cold head on the 
    ICE Oxford cryostat
    
    Construction
    ------------
    ``cooler = f70('visa_name')``

    visa_name : string, required
        The address of the instrument, e.g. ``'com1'``
        
    Methods 
    -------
    start
    stop
    reset
    coldhead_only_start
    coldhead_pause
    coldhead_resume
    print_status : prints a human readable interpetation of the status bytes
    
    Dynamic Properties (all get only)
    ----------
    temperatures : list of floats [He discharge , water outlet , water inlet] 
                   in degrees centigrade
    he_return_pressure : int, in PSI gauage 
    state : list of booleans see function docstring for more info or try
            print_staus() for a human-freindly version
    hours_run : float
    firmware_version : string
        
    """
        
    def _setup(self):
        """ Configure serial """
        self._pyvisa.read_termination = '\r'
        self._pyvisa.write_termination = '\r'
        self._pyvisa.baud_rate = 9600
        
        
    """ the chiller doens't support *IDN. It will reply with an invlaid message
    string "$???,3278" so I'm going to use this as an idstring. This will not 
    allow us to differentiate between compressors in future, but should be
    unique among the instruments we have currently. There is an $ID1 command, 
    but this may not be unique to each compressor either"""
    
    _idnstring = "$???"#",3278"

    """OK, I'm going to be lazy.  I never have to set a vairable, so there 
    are a limited number of possibe commands.  Rather than calculate CRCs,
    I'm just going to pre-compute each command string including it's CRC
    
    I'm also dropping the CRCs on the replies. I haven't bothered to check the
    echoed commands because the system will echo even if the command was 
    unsucsessfull"""
    #TODO check the echo, try again if wrong, and raise error if still wrong

    
    """ ++++++++++++ User Propertites ++++++++++++ """
    
    @property
    def temperatures(self):
        """gets all temperatures in degrees centigrade and returns them as a 
        list [Helium compressor dicharge , water outlet , water inlet]"""
        resp = self.raw_query("$TEAA4B9")
        resp = resp.split(",")
        temps = [float(resp[1]), float(resp[2]), float(resp[3])]
        return temps
    
    @property
    def he_return_pressure(self):
        """gets the Helim return pressure in PSI guage"""
        #TODO - check units shown on front panel guages and convert to match
        resp = self.raw_query("$PRA95F7")
        pres = resp.split(",")[1]
        return float(pres)
    
    @property
    def state(self):
        """get the status bytes and convert into a list of booleans. For 
        human-frendly interpretation try print_status(). The list idicies are 
        the same as the manual (i.e. [0] is system on/of and [15] is comms 
        config) Some usefull bits are:
        [0] system on
        [1] motor temp alarm
        [2] phase sequence / phase loss / blown fuse alarm
        [3] helium temperature alarm
        [4] water temperature alarm (high inlet temp)
        [5] water flow alarm (high outlet temp)
        [6] oil level alarm
        [7] pressure alarm
        [8] Selenoid on 
        """
        resp = self.raw_query("$STA3504")
        bits = resp.split(",")[1]
        binary = bin(int(bits, base=16))
        bitstring = binary[2:].zfill(16) # drop 0b and recover leading zeros
        booleanlist = [bool(int(bit)) for bit in bitstring]
        booleanlist.reverse() # it sends bit 15 first
        return booleanlist
    
    @property
    def state_int(self):
        """see state
        """
        resp = self.raw_query("$STA3504")
        bits = resp.split(",")[1]
        return int(bits, base=16)
  
    @property
    def hours_run(self):
        """gets the total hours run"""
        resp = self.raw_query("$ID1D629")
        hours = resp.split(",")[2]
        return float(hours)  

    @property
    def firmware_version(self):
        """gets the firmaware version. Probaby a number but handled as a string 
        just in case"""
        resp = self.raw_query("$ID1D629")
        vers = resp.split(",")[1]
        return vers  
        
        
    """ ++++++++++++ User Methods ++++++++++++ """
    
    def start(self):
        """Starts the compressor and cold head, unless an error is present"""
        self.raw_query("$ON177CF")

    def stop(self):
        """Stops the compressor and cold head"""
        self.raw_query("$OFF9188")

    def reset(self):
        """Resets the fault memeory, but current faults will persist"""
        self.raw_query("$RS12156")

    def coldhead_only_start(self):
        """Starts the cold head but not the compressor.  Stops after 30 mins"""
        self.raw_query("$CHRFD4C")

    def coldhead_pause(self):
        """Pause the cold head. Compressor keeps running. Use coldhead_resume() 
        to resume"""
        self.raw_query("$CHP3CCD")

    def coldhead_resume(self):
        """reverses coldhead_pause()"""
        self.raw_query("$POF07BF")
        
    def print_status(self):
        """Fetch the status bytes, and print a human-freindly interpretation"""
        cachestate = self.state
        print("\n ========== Alarms ==========")
        print("Motor temperatrue alarm   ",cachestate[1])
        print("Phase sequence alarm      ",cachestate[2])
        print("Helium Temperatrue alarm  ",cachestate[3])
        print("water temperature alarm   ",cachestate[4])
        print("low water flow alarm      ",cachestate[5])
        print("oil level alarm           ",cachestate[6])
        print("Low helium pressure alarm ",cachestate[7])
        print ("\n ========= Other =========")        
        if cachestate[0] == True:
            print("The System is ON")
        else:
            print("The system is OFF")
        if cachestate[8] == True:
            print("The Selenoid is ON (closed)")
        else:
                print("The Selenoid is OFF (open)")
        if cachestate[15] == True:
            print("The control configuration is: mode 2 (RS232 contol not possible)")
        else:
            print("The control configuration is: mode 1 (this is normal)")
        if cachestate[9:12] == [True,True,True]:
            print("The STATUS string is: Oil Fault Off")
        elif cachestate[9:12] == [False,True,True]:
            print("The STATUS string is: Fault Off")
        elif cachestate[9:12] == [True,False,True]:
            print("The STATUS string is: Cold Head Pause")
        elif cachestate[9:12] == [False,False,True]:
            print("The STATUS string is: Cold Head Run")
        elif cachestate[9:12] == [True,True,False]:
            print("The STATUS string is: Remote On")
        elif cachestate[9:12] == [False,True,False]:
            print("The STATUS string is: Remote Off")
        elif cachestate[9:12] == [True,False,False]:
            print("The STATUS string is: Local On")
        elif cachestate[9:12] == [False,False,False]:
            print("The STATUS string is: Local Off")