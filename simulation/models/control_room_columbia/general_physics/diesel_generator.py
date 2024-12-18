from simulation.constants.electrical_types import ElectricalType
from simulation.constants.equipment_states import EquipmentStates
from simulation.models.control_room_columbia.general_physics import ac_power
from simulation.models.control_room_columbia import model
from simulation.models.control_room_columbia.libraries import pid
import math
import log

class DieselGenerator():
    def __init__(self,name,cs = "",output = "",sa = 500,auto = False,loca = False,trip = False,lockout = False,voltage = 0,frequency = 0,annunciators={},inertia = 0,horsepower = 0,):
        self.name = name
        self.dg = {
            "state" : EquipmentStates.STOPPED,
            "control_switch" : cs,
            "output_breaker" : output,
            "last_rpm" : 0,
            "rpm" : 0, #normal is 900
            "rpm_set" : 900,
            "throttle" : 0,
            "volt_reg" : 1,
            "current" : 0,
            "field_voltage" : 0,
            "angular_velocity" : 0,
            "start_air_press" : sa,
            "auto_start" : auto,
            "loca_start" : loca,
            "trip" : trip,
            "lockout" : lockout,
            #TODO: voltage regulator/rpm governor
            "voltage" : voltage,
            "frequency" : frequency, #8 pole generator. 60hz@900rpm
            "annunciators" : annunciators,
            "time" : 0,
        }
        self.physics_constants = {
            "horsepower" : horsepower,
            "inertia" : inertia,
        }
        self.governor_pid = pid.PIDExperimental(0.19,0,0.1,-0.05,0.05) #pid.PID(0.25,0.001,0.01,-0.2,0.2)
        self.accel_pid = pid.PID(0.3,0.0001,0.001,-0.3,0)
        #self.exciter_pid = pid.PID(0.05,0.0002,0.002,-0.5,0.5)

    def can_start(self):
        """Returns true if the DG is not tripped,locked out, or starting already"""
        return not self.dg["lockout"] and not self.dg["trip"] and self.dg["state"] == EquipmentStates.STOPPED

    def start(self,auto = False):
        """Starts the diesel generator"""
        if self.can_start():
            self.dg["state"] = EquipmentStates.STARTING
            if auto:
                self.dg["auto_start"] = True

    def can_stop(self):
        """Returns true if the DG is able to be stopped normally."""
        return self.dg["state"] == EquipmentStates.RUNNING
    
    def stop(self):
        """Stops the diesel generator normally."""
        if self.can_stop():
            self.dg["state"] == EquipmentStates.STOPPING
            self.dg["auto_start"] = False

    def check_controls(self):
        """Default start/stop control switch for the diesel generator.
        This does NOT have to be used, you can use start(), and stop()"""
        if self.dg["control_switch"] in model.switches:
            cont_sw = model.switches[self.dg["control_switch"]]

            if cont_sw["position"] == 0:
                #a loca autostart prevents this?
                if self.dg["state"] == EquipmentStates.RUNNING:
                    self.dg["state"] = EquipmentStates.STOPPING

            if cont_sw["position"] == 2:
                #TODO: flag position autostart alarm clear (and running alarm?)
                if self.dg["state"] == EquipmentStates.STOPPED:
                    self.dg["state"] = EquipmentStates.STARTING

            if "green" in cont_sw["lights"]:
                cont_sw["lights"]["green"] = self.dg["state"] == EquipmentStates.STOPPED
                cont_sw["lights"]["red"] = self.dg["state"] != EquipmentStates.STOPPED

    def calculate(self):
        #huge thanks to @fluff.goose (discord) for help with this
        throttle = self.dg["throttle"]

        if self.dg["trip"]:
            self.dg["state"] = EquipmentStates.STOPPING

        horsepower = self.physics_constants["horsepower"]

        torque = (horsepower*5252)/900

        torque = torque*throttle

        total_load = 0

        for load in ac_power.sources[self.name].info["loads"]:
            total_load += ac_power.sources[self.name].info["loads"][load]

        generator_load = total_load

        generator_torque = ((generator_load/746)*5252)/900 #746 watts is 1 horsepwer

        generator_omega = generator_torque/self.physics_constants["inertia"] #slows down the engine when its loaded

        omega = torque/self.physics_constants["inertia"]

        omega -= (self.dg["angular_velocity"]*0.003)

        self.dg["angular_velocity"] = self.dg["angular_velocity"]+((omega-generator_omega)*10) #rad/s

        self.dg["angular_velocity"] = max(self.dg["angular_velocity"],0)

        self.dg["rpm"] = self.dg["angular_velocity"]*60/(2*math.pi) 

        #self.dg["time"] += 0.1 #aids in testing start times

        if self.dg["rpm"] >= 900:
            self.dg["state"] = EquipmentStates.RUNNING
            #log.info(str(self.dg["time"]))
            #exit()

        if self.dg["rpm"] <= 50 and self.dg["state"] == EquipmentStates.STOPPING:
            self.dg["state"] = EquipmentStates.STOPPED
            self.dg["angular_velocity"] = 0

        #TODO: Voltage regulator

        self.dg["frequency"] = 60*(self.dg["rpm"]/900)
        self.dg["voltage"] = 4160*(self.dg["rpm"]/900)

        self.dg["current"] = generator_load/(self.dg["voltage"]+0.1)

        #log.info(str(self.dg["voltage"]))

        ac_power.sources[self.name].info["voltage"] = self.dg["voltage"]
        ac_power.sources[self.name].info["frequency"] = self.dg["frequency"]

        if False:

            field_voltage = 0 #come on you know what this is in
            field_resistance = 20 #ohms

            field_voltage = self.dg["voltage"]*0.15*self.dg["volt_reg"] #TODO: get a general field voltage later

            #Excitier
            #Columbia has Static Field Flashing
            if self.dg["rpm"] > 350 and self.dg["voltage"] < 1000:
                #Flash the field
                field_voltage += 12

            field_current = field_voltage/field_resistance

            self.dg["voltage"] = field_current*self.dg["angular_velocity"]
            self.dg["field_voltage"] = field_voltage


        


    def governor(self):
        pid_output = self.governor_pid.update(self.dg["rpm_set"],self.dg["rpm"],1)

        self.dg["throttle"] = max(min(self.dg["throttle"]+pid_output,1),0)

        if self.dg["state"] == EquipmentStates.STARTING:
            acceleration = self.dg["rpm"] - self.dg["last_rpm"]

            pid_output = self.accel_pid.update(15,acceleration,1)

            self.dg["throttle"] = max(min(self.dg["throttle"]+pid_output,1),0)

        if self.dg["state"] == EquipmentStates.STOPPED or self.dg["state"] == EquipmentStates.STOPPING:
            self.dg["throttle"] = 0

        self.dg["last_rpm"] = self.dg["rpm"]

    def volt_reg(self):
        #The voltage regulator controls the Exciter
        #https://www.nrc.gov/docs/ML1122/ML11229A143.pdf

        #pid_output = self.exciter_pid.update(4160,self.dg["voltage"],1) #TODO: Voltage Regulator adjust

        #self.dg["volt_reg"] = max(min(self.dg["volt_reg"]+pid_output,2),0)
        a = ""



dg1 = None
dg2 = None
dg3 = None

def initialize():
    global dg1
    global dg2
    global dg3
    dg1 = DieselGenerator("DG1",cs = "diesel_gen_1",output = "cb_dg1_7",inertia=36000,horsepower=6000)
    dg2 = DieselGenerator("DG2",cs = "diesel_gen_2",output = "cb_dg2_8",inertia=36000,horsepower=6000)
    dg3 = DieselGenerator("DG3",cs = "diesel_gen_3",output = "cb_dg3_4",inertia=36000,horsepower=6000)

def run():
    dg1.check_controls()
    dg1.calculate()
    dg1.governor()
    #dg1.volt_reg()

    dg2.check_controls()
    dg2.calculate()
    dg2.governor()
    #dg2.volt_reg()

    dg3.check_controls()
    dg3.calculate()
    dg3.governor()
    #dg2.volt_reg()