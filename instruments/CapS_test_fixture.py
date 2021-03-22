#
# Copyright 2016-2021 Razorbill Instruments Ltd.
# This file is part of the Razorbill Lab Python library which is
# available under the MIT licence - see the LICENCE file for more.
#


import numpy
import time
import threading
import os
from math import sin, cos, tan, atan2, radians, degrees, sqrt
from instruments import razorbill
from instruments.micro_epsilon.capa_ncdt import DT62xx
from instruments.homemade  import Motor_Driver,BenchCapacitanceMeter
from instruments.keysight_lcr import E4980A
from controllers.controllers import PID
from measurement import setup_environment, Quantity
from measurement.recorders import AutoRecorder, Recorder

#TODO fix the +200 kludge used to prevent zta getting fed negative numbers


"""this is a dictionary of positions of actuators and sensors angles are in 
degrees, radii are in mm, ranges are in microns
actuators are named X,Y,Z going clockwise. 
the next sensor clockwise after each actuator shares it's letter.
"""
acctuators = {"alphaX":0,
              "alphaY":120,
              "alphaZ":240,
              "radius":40 }
CS02 = {"alphaX":45,
        "alphaY":165,
        "alphaZ":285,
        "radius":65, 
        "range":200,
        "sensor_dia":2300}
CS1 = {"alphaX":70,
       "alphaY":190,
       "alphaZ":310,
       "radius":65, 
       "range": 1000,
       "sensor_dia":5700}
calibration = {"ecc_dist":28, #microns
               "ecc_dir":300,  #degrees
               "tip_angle":1.32, #mRad
               "tip_dir":67.7, #degrees
               "uE_offsets":[340,324,327]} #microns

def _zta_to_height(zta,pos):
    """ calculates a height at some position (angle, radius) from a Z theta
     alpha input. it returns a list of heights [x,y,z] 
    
    typical use:
        height_at_sensor_or_actuator = zta_to_height(meas_point,CS02)
        where meas point is a list of [z,theta,alpha] and CS02 is a dict from
        the top of this file
    """
    height = [( zta[0] - (pos["radius"]*1000) * (zta[1]/1000) * cos(radians(pos["alphaX"]-zta[2])) ),
              ( zta[0] - (pos["radius"]*1000) * (zta[1]/1000) * cos(radians(pos["alphaY"]-zta[2])) ),
              ( zta[0] - (pos["radius"]*1000) * (zta[1]/1000) * cos(radians(pos["alphaZ"]-zta[2])) )]
    return(height)       

def height_to_zta(heights, pos):
    """ calculates a zta from a set of three actuator or sensor heights (x,y,z) 
    
    typical use:
        zta = _height_to_zta(xyz,CSO2)
        where xyz is a list of heights [x,y,z] and CS02 is a dict 
        from the top of this file
    """ 
    #Z    
    z = sum(heights) / 3  
    #alpha - lets convert to cartesian cordinates (um), where alpha = 0 on the x axis
    x1= pos["radius"]*1000 * cos(radians(pos["alphaX"]))
    y1= pos["radius"]*1000 * sin(radians(pos["alphaX"])) 
    x2= pos["radius"]*1000 * cos(radians(pos["alphaY"]))
    y2= pos["radius"]*1000 * sin(radians(pos["alphaY"]))
    x3= pos["radius"]*1000 * cos(radians(pos["alphaZ"]))
    y3= pos["radius"]*1000 * sin(radians(pos["alphaZ"])) 
    # next, find the normal vector of a plane through those points
    vector1 = [x1-x2 , y1-y2 , heights[0]-heights[1]] # vector from 0 to 1
    vector2 = [x1-x3 , y1-y3 , heights[0]-heights[2]] # vector from 0 to 2
    normal_vector = [vector1[1]*vector2[2] - vector1[2]*vector2[1], # cross product
                     vector1[2]*vector2[0] - vector1[0]*vector2[2],
                     vector1[0]*vector2[1] - vector1[1]*vector2[0]]
    # calculate alpha from normal vector (math.atan2 returns the correct quadrant and avoides div0 errors in math.atan)
    alpha = atan2(normal_vector[1],normal_vector[0]) 
    alpha = degrees(alpha)
    if alpha < 0: alpha = alpha + 360
    #theta - convert normal vector to unit vector
    length = sqrt(normal_vector[0]**2+normal_vector[1]**2+normal_vector[2]**2)
    unit_vector = [normal_vector[0]/length, normal_vector[1]/length, normal_vector[2]/length]
    #project the unit vector onto the x-y plane
    theta = sqrt(unit_vector[0]**2 + unit_vector[1]**2)
    #correct for small angle asumption
    theta = sin(theta)       
    return [z,theta*1000,alpha]
                
	  
class Plan:
    """
    This is the motion planner for the measurements and movements of the CapS test 
    fixture
    
    This class stores the list of measurement points and contains methods to
    plan motion, check the range of the uE sensors is sufficient for the planned
    motion, etc.
    """
    def __init__(self):
        self.meas_points = []     # a list of points at which measurements will be taken [z,t,a]
        self.meas_points_offset = [] # above list corrected for eccentricty/tip of DUT
        self.point_count = 0      # the number of points in MeasPoints
        self.sensor = CS02        # which sensor set to use. defaults to CS02.
        self.meas_points_ue = []  # measurement points in terms of the uE sensor readings[x,y,z,]
        self.meas_points_acc = [] # measurement points in terms of actuator positions [x,y,z]
        self.max_ue = [0,0,0]     # the range required for the sensors [x,y,z] 
        self.min_ue = [0,0,0]     # the range required for the sensors [x,y,z] 
        self.max_acc = [0,0,0]    # the range required for the actuator [x,y,z]
        self.min_acc = [0,0,0]    # the range required for the actuator [x,y,z]
    
    class PlanError(Exception):
        pass
    
    def run_planner(self):
        """ this function runs the planner. It has no arguments and returns nothing"""
        print("calculating moves...")
        self._count_points()
        self._cal_meas_points()
        self._calc_ue()
        self._calc_acc()
        print((self.point_count), "Measurement points were generated")
        
        if self.max_ue[0] - self.min_ue[0] > self.sensor["range"]:
            raise self.PlanError("The plan exceedes the range of sensor 1")
        if self.max_ue[1] - self.min_ue[1] > self.sensor["range"]:
            raise self.PlanError("The plan exceedes the range of sensor 2")
        if self.max_ue[2] - self.min_ue[2] > self.sensor["range"]:
            raise self.PlanError("The plan exceedes the range of sensor 3")
      
    def correction(self,ue_error):
        """ calculate the actuations required to correct an error in position,
        where position is expressed in terms of deviation from target readings 
        for the micro epsilon sensors
        
        returns a list of actuations [x,y,z]
        
        typical use:
            actuation = correction(ue_error)
            where both acctuation and ue_error are lists [x,y,z] in microns
        """
        z_error = numpy.mean(ue_error[:])                      # the mean error is the z error 
        ratio = (acctuators["radius"] / self.sensor["radius"]) # calculate the ratio of radii 
        
        # the next block calculates the actuations as if the PCD were the same
        acctuation = [0,0,0]
        acctuation[0] =  (ue_error[0] * cos(radians( acctuators["alphaX"] - self.sensor["alphaX"] ))
                        + ue_error[1] * cos(radians( acctuators["alphaX"] - self.sensor["alphaY"] ))
                        + ue_error[2] * cos(radians( acctuators["alphaX"] - self.sensor["alphaZ"] )))
        acctuation[1] =  (ue_error[0] * cos(radians( acctuators["alphaY"] - self.sensor["alphaX"] ))
                        + ue_error[1] * cos(radians( acctuators["alphaY"] - self.sensor["alphaY"] ))
                        + ue_error[2] * cos(radians( acctuators["alphaY"] - self.sensor["alphaZ"] )))
        acctuation[2] =  (ue_error[0] * cos(radians( acctuators["alphaZ"] - self.sensor["alphaX"] ))
                        + ue_error[1] * cos(radians( acctuators["alphaZ"] - self.sensor["alphaY"] ))
                        + ue_error[2] * cos(radians( acctuators["alphaZ"] - self.sensor["alphaZ"] )))
        
        # this block corrects for PCD and adds the z offset (which disappears in the above maths)
        acctuation[0] = - (acctuation[0] * ratio + z_error)
        acctuation[1] = - (acctuation[1] * ratio + z_error)
        acctuation[2] = - (acctuation[2] * ratio + z_error)        
        return acctuation
        
    def _count_points(self):
        """ Function counts the number of measurement points in the plan
        and updates the point count accordigly. It has no arguments and returns nothing
        """
        self.point_count = len(self.meas_points)
        
    def _cal_meas_points(self):
        for n in range(self.point_count): 
            self.meas_points_offset.append(self._calibrate(self.meas_points[n],1))   
            
    def _calibrate(self,zta,direction):
        """ function for shifting the coordinate space to take account of 
        eccentricity or tip in the sensor under test.  Calibration data is from
        a dict at the top of the file
        direction is 1 for applying a corrections, -1 for removing it."""
        if direction != 1 and direction != -1:
            raise self.PlanError("calibration direction must be 1 or -1")
        tip1 = zta[1]* cos(radians(zta[2])) + direction*calibration["tip_angle"]* cos(radians(calibration["tip_dir"]))
        tip2 = zta[1]* sin(radians(zta[2])) + direction*calibration["tip_angle"]* sin(radians(calibration["tip_dir"]))
        theta = sqrt(tip1**2 + tip2**2)
        alpha = degrees(atan2(tip2,tip1))
        if alpha < 0: alpha = alpha + 360
        #for z we don't need the decomposed axes, but we do need theta and alpha 
        if direction == 1:
            z = zta[0] + sin(zta[1]/1000)*calibration["ecc_dist"]*cos(
                                    radians((zta[2] - calibration["ecc_dir"]))) 
        else:
            z = zta[0] - sin(theta/1000)*calibration["ecc_dist"]*cos(
                                    radians((alpha - calibration["ecc_dir"]))) 
        return([z,theta,alpha])
    
    def _calc_ue(self):
        """ Function populates the projected positions for the micro
        epsilon sensors. It has no arguments and returns nothing
        """
        for n in range(self.point_count):
            ue_point = _zta_to_height(self.meas_points_offset[n],self.sensor)
            for ch in [0,1,2]:    
                ue_point[ch] = ue_point[ch] + calibration["ue_offsets"][ch]
            self.meas_points_ue.append(ue_point)         
        # calculate max and min positions for each sensor
        for ch in [0,1,2]:
            self.max_ue[ch] = max([sublist[ch] for sublist in self.meas_points_ue])                     
            self.min_ue[ch] = min([sublist[ch] for sublist in self.meas_points_ue])
            if self.min_ue[ch] > 0: self.min_ue[ch] = 0 # the system needs to return to [0,0,0] at the end

    def _calc_acc(self):
        """ this function populates the projected positions for the actuators
        It has no arguments and returns nothing
        """
        for n in range(self.point_count):
            acc_point = _zta_to_height(self.meas_points_offset[n],acctuators)
            self.meas_points_acc.append (acc_point)       
        # calculate max and min positions for each sensor
        for ch in [0,1,2]:
            self.max_acc[ch] = max([sublist[ch] for sublist in self.meas_points_acc]) 
        for ch in [0,1,2]:                           
            self.min_acc[ch] = min([sublist[ch] for sublist in self.meas_points_acc])



class _Special_PID:
    """ a variant of controllers.AutoPID that can work with three
    interleved channels and other hardware oddities specific to the 
    test fixture"""    

    def __init__(self, setpoints, get_sensor, _set_voltage, init_voltages, plan):
        self._stopping = False
        self._interval = 0.05
        self.voltages = init_voltages
        self.move_at_sensor = [None,None,None]
        P = 1.2
        I = 3
        D = 0.15
        self.pid = [PID(p=P, i=I, d=D),PID(p=P, i=I, d=D),PID(p=P, i=I, d=D)]
        for ch in [0,1,2]:
            self.pid[ch].set_point = setpoints[ch]
            self.pid[ch].start()
        time.sleep(self._interval)
        
        def _callback():
            while not self._stopping:
                for ch in [0,1,2]:
                    self.move_at_sensor[ch] = self.pid[ch].update(get_sensor()[ch])
                move = plan.correction(self.move_at_sensor)                
                for ch in [0,1,2]: 
                    self.voltages[ch] = self.voltages[ch] - move[ch] #the correction routine reverses sign   
                    _set_voltage(ch,self.voltages[ch])
                time.sleep(self._interval)
                
        self._thread = threading.Thread(target=_callback, name="Piezo_PID")

    def start(self):
        """ Start PID control"""
        self._thread.start()

    def stop(self):
        """ Stop controller and clean up. May block for up to _interval"""
        self._stopping = True
        self._thread.join()


class TestFixture:
    
    def __init__(self,plan):
        self.plan = plan
        print("establishing communication with instruments...")
        self.uE = DT62xx("169.254.168.150", num_channels=3)
        self.PS1 = razorbill.RP100("com4")
        self.PS2 = razorbill.RP100("com10")
        self.motors = Motor_Driver("ASRL5::INSTR")
        print("setting up variables...")
        setup_environment()
        self.pz_channels = [self.PS1.channels[1],self.PS1.channels[2],self.PS2.channels[1]]
        self.ue_offset = calibration["uE_offsets"]    
        print("slewing power supplies to starting voltage...")        
        for channel in self.pz_channels:
            channel.enable = True
            channel.slew_rate = 500
            channel.voltage_set = 50
        time.sleep(1) # wait for PS to slew to 50
    
    class TF_Error(Exception):
        pass
    
    def _get_sensors(self):
        measurement = self.uE.channels[0].measure
        output = [None,None,None]
        zta = height_to_zta(measurement,self.plan.sensor)
        for i in [0,1,2]:
            output[i] = measurement[i]* ( 1+  
                                  (self.plan.sensor["sensor_dia"]/1e6/2)**2 *tan(zta[1]/1000)**2
                                 /(4*measurement[i]/1e6)**2)
        return  output

    def _set_voltage(self,channel,voltage):
        voltage = self._voltage_check(voltage, channel)
        self.pz_channels[channel].voltage_set = voltage
    
    def _set_voltage_rel(self,channel,voltage_change):
        voltage = self.pz_channels[channel].voltage_now + voltage_change
        voltage = self._voltage_check(voltage,channel)
        self.pz_channels[channel].voltage_set = voltage
        return voltage

    def _voltage_check(self,voltage,channel):  
        max_volt = 100
        min_volt = 0
        if voltage > max_volt:
            voltage = max_volt
            print("overvoltage clamped on ",channel)
        if voltage < min_volt:
            voltage = min_volt
            print("undervoltage clamped on ",channel)
        return voltage
    
    def zero_sensors(self):
        print("Zeroing sensors...")
        for ch in [0,1,2]:
            current = self.uE.channels[ch +1].measure
            if (current + self.plan.max_ue[ch]) < self.plan.sensor["range"]  \
            and  (current - self.plan.min_ue[ch]) > 0:
                self.ue_offset[ch] = current
            else: self._move_sensor(ch, self.plan)
            
    def _move_sensor(self, ch, plan):
        """function for adjusting a sensor in it's collet, shows live data in KST
        it assumes the TF is at zero"""
        maximum = plan.sensor["range"] - plan.max_ue[ch] 
        minimum = - plan.min_ue[ch] 
        if minimum < 0: minimum = 0
        pos = Quantity("position", (self.uE.channels[ch+1],"measure"),"um")
        temp_rec = AutoRecorder("temp", [pos], 0.1, plot_kst = True, overwrite = True)
        print("adjust sensor", ch+1, "to \n MAX:", maximum, "\n MIN:", minimum)
        input("then press enter to continue")
        temp_rec.stop()
        try:
            os.remove("temp.csv")
        except:
            print("error deleting temp file. Continuing...")
        self.zero_sensors()
    
    def _uE_error(self,setpoints):
        ue_error =[None,None,None]
        measurement = self._get_sensors()
        for ch in [0,1,2]:
            ue_error[ch] = measurement[ch] - setpoints[ch]
        return ue_error
      
    def movemotors(self, setpoints):
        """ use motors to move to a coarse position
        setpoints is a list of acctuator poitions [X,Y,Z]
        the system will make 3 attempts to reach the setpoint"""
        for attempt in (range (3)):
            ue_error = self._uE_error(setpoints)
            move = self.plan.correction(ue_error)
            self.motors.move_rel(move)
            time.sleep(0.2)
    
    def movemotors_zta(self,zta):
        self.movemotors(_zta_to_height(zta,acctuators))
    
    def movepz(self, setpoints):
        """ move to a fine position, seperate from PID in order to get fast slew 
        without causing oscilations"""
        for i in range(2):
            uE_error = self._uE_error(setpoints)
            move = self.plan.correction(uE_error)
            voltchange = [None,None,None]
            voltchange[0] = move[0] * (100/36)
            voltchange[1] = move[1] * (100/36)
            voltchange[2] = move[2] * (100/36)
            voltset = [None,None,None]
            voltset[0] = self._set_voltage_rel(0,voltchange[0])
            voltset[1] = self._set_voltage_rel(1,voltchange[1])
            voltset[2] = self._set_voltage_rel(2,voltchange[2])
            time.sleep(0.5) # allow system to slew before next loop
        return voltset
                
    def hold_position(self,setpoints, init_voltage):
        """ use PID to move to and hold a position
        setpoints is a list of acctuator poitions [X,Y,Z]"""
        self.pid = _Special_PID(setpoints, self._get_sensors, self._set_voltage, init_voltage, self.plan)             
        self.pid.start()
 
    def release_position(self,usemotors):
        self.pid.stop()
        if usemotors == True:
            for channel in self.pz_channels:
                channel.voltage_set = 50

    def powerdown(self):
        """ switch off the power supples (make safe)"""
        for channel in self.pz_channels:
            channel.voltage_set = 0
        time.sleep(1)
        for channel in self.pz_channels:
            channel.enable = False
        print("power supplies shut down")
        
    def setup_measurement_equptment(self,cap_device,experiment_name):
        if cap_device == "bridge":
            bridge = E4980A('USB0::0x0957::0x0909::MY54202895::INSTR')
        elif cap_device == "BCM":
            BCM = BenchCapacitanceMeter("com9")
        else: raise self.TF_Error("capacitance measurement device was not 'bridge' or 'BCM'")
        self.setpoint_ht_sensors = [0,0,0] # will be updated in the loop later, defined here so that the recorders can be set up          
        self.zta = [0,0,0]
        
        sensor_heights = Quantity(["height x","height y","height z"],
                                  self._get_sensors,
                                  ["um","um","um"])
        set_ht_sensors = Quantity(["X sensor setpoint","Y sensor setpoint","Z sensor setpoint"],
                              (self,"setpoint_ht_sensors"), 
                              ["um","um","um"])
        zta = Quantity(["Z", "theta","alpha"], (self, "zta"), ["um","mRad","deg"])
        voltage1 = Quantity("voltage1", (self.pz_channels[0], "voltage_now"), "V")
        voltage2 = Quantity("voltage2", (self.pz_channels[1], "voltage_now"), "V")
        voltage3 = Quantity("voltage3", (self.pz_channels[2], "voltage_now"), "V")
        if cap_device == "bridge":
            self.cap = Quantity(['Capacitance', 'loss'], (bridge, 'meas'), 
                                ['pF','GOhm'],scalefactor=[1e12, 1e-9] )
        elif cap_device == "BCM":
            self.cap = Quantity("Capacitance", (BCM.channels[1], "capacitance"), "pF")
                
        self.rec = Recorder(experiment_name + " measurement data", 
                            [zta, self.cap], 
                            plot_kst=True)
        self.a_rec = AutoRecorder(experiment_name + " debug data",
                                  [set_ht_sensors,
                                  voltage1, voltage2, voltage3,
                                  sensor_heights, 
                                  self.cap],
                                  0.01, plot_kst=True)

    def run_experiment(self,use_motors,hold_period, repeats, interval):
        for point in range(self.plan.point_count):
            print("\rmeasuring point", point +1, "of", self.plan.point_count, end = "    ")
            #get the setpoints to where the recorders can see them
            self.setpoint_ht_sensors = self.plan.meas_points_ue[point]
            # move to position
            if use_motors == True:
                self.movemotors(self.plan.meas_points_ue[point])
            init_voltages=self.movepz(self.plan.meas_points_ue[point])
            # do the measurement
            self.hold_position(self.plan.meas_points_ue[point], init_voltages)
            time.sleep(hold_period)
            for i in range(repeats):
                position = self._get_sensors()
                for ch in [0,1,2]:
                    position[ch] = position [ch] - self.ue_offset[ch]
                self.zta = self.plan._calibrate(height_to_zta(position,self.plan.sensor),-1)
                self.rec.record_line()
                time.sleep(interval)                
            self.release_position(use_motors) 
          
        # measurements complete, tidy up
        if use_motors == True:
            self.setpoint_ht_sensors = self.ue_offset
            self.movemotors(self.ue_offset)            
        print("\nexperiment complete")
        time.sleep(1)
        self.rec.stop()
        self.a_rec.stop()