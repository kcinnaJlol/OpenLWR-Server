from simulation.constants.electrical_types import ElectricalType
from simulation.constants.equipment_states import EquipmentStates
from general_physics import ac_power
from control_room_nmp2 import model
import math

def clamp(val, clamp_min, clamp_max):
    return min(max(val,clamp_min),clamp_max)

from enum import IntEnum

class PumpTypes(IntEnum):
    Type1 = 0


headers = { #most lines have a common header that they discharge into
    #this header can pressurize and etc.
    #takes a pipe diameter and length.
    #This also allows us to simulate the header depressurizing (level is not 100% full, happens through pinpoint cracks and whatnot.)
    "hpcs_discharge_header" : {
        #This next comment will be present on ALL headers.
        #it indicates the real pipe that this header was made from.
        #16" HPCS(1)-4-1

        "diameter" : 406.40, #millimeters
        "length" : 0, #TODO : determine a good length
        "pressure" : 0, #pascals
        "volume" : 0, #Initialized on start. Is not changed again.
    }

}

def initialize_pumps():
    for pump_name in model.pumps:
        pump = model.pumps[pump_name]

        pump_created = pump_1 #TODO: actual types

        for value_name in pump:
            value = pump[value_name]
            if value_name in pump_created:
                pump_created[value_name] = value

        model.pumps[pump_name] = pump_created

def run():
    for pump_name in model.pumps:
        pump = model.pumps[pump_name]

        if pump["motor_breaker_closed"]:
            #first, verify that this breaker is allowed to be closed

            #TODO: overcurrent breaker trip

            #undervoltage breaker trip TODO: (this has load sequencing during a LOOP? verify this)

            pump_bus = ac_power.busses[pump["bus"]]

            if pump_bus["voltage"] < 120:
                pump["motor_breaker_closed"] = False

            Acceleration = (pump["rated_rpm"]-pump["rpm"])*0.1 #TODO: variable motor accel
            pump["rpm"] = clamp(pump["rpm"]+Acceleration,0,pump["rated_rpm"]+100)
            #full load amperes
            AmpsFLA = (pump["horsepower"]*746)/(math.sqrt(3)*pump_bus["voltage"]*0.876*0.95) #TODO: variable motor efficiency and power factor
            pump["amperes"] = (AmpsFLA*clamp(pump["actual_flow"]/pump["rated_flow"],0.48,1))+(AmpsFLA*5*(Acceleration/(pump["rated_rpm"]*0.1)))
            pump["watts"] = pump_bus["voltage"]*pump["amperes"]*math.sqrt(3)

			#remember to make the loading process for the current (v.FLA*math.clamp(v.flow_with_fullsim etc)) more realistic, and instead make it based on distance from rated rpm (as when the pump is loaded more it will draw more current)
        else:
            Acceleration = (pump["rpm"])*0.1 #TODO: variable motor accel
            pump["rpm"] = clamp(pump["rpm"]-Acceleration,0,pump["rated_rpm"]+100)
            pump["amperes"] = 0
            pump["watts"] = 0
    

