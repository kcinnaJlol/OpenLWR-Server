import math

AtomicNumberDensities = {
	"U235" : 2.53*(10**22),
	"U238" : 2.51*(10**22),
}

from simulation.models.control_room_columbia.reactor_physics.cross_sections import MicroscopicCrossSections
from simulation.models.control_room_columbia.reactor_physics.cross_sections import MacroscopicCrossSections

def clamp(val, min, max):
	if val < min: return min
	if val > max: return max
	return val


def get(waterMass, controlDepth, neutronFlux, temperatureFuel, CoreFlow):
    #TODO: Core flow (percent of 100)
    #TODO: Improve code quality

    N235 = AtomicNumberDensities["U235"]
    N238 = AtomicNumberDensities["U238"]

    MacroscopicU235 = 1+(N235*MicroscopicCrossSections["Fuel"]["U235"]["Thermal"]["Capture"])+(N238*MicroscopicCrossSections["Fuel"]["U238"]["Thermal"]["Capture"])
    ReproductionFactor = (2.43*MacroscopicU235)/(MacroscopicU235+(MicroscopicCrossSections["Fuel"]["U235"]["Thermal"]["Capture"]*N235*0.435))
    U235SumCrossSection = (N235*MicroscopicCrossSections["Fuel"]["U235"]["Thermal"]["Fission"]) + (N235*MicroscopicCrossSections["Fuel"]["U235"]["Thermal"]["Capture"])
    CR = controlDepth
	
    voids = neutronFlux/(2500000000000)

    CoreFlow = CoreFlow

    CoreFlow = clamp(abs((CoreFlow/100)-1),0,1)

    voids = clamp(CoreFlow*voids,0,1)

    voids = clamp(voids,0,0.7)

    CR+=voids
    #CR+=(_G.SLCPentaborateGallons/4800)*0.7 #This was a value left over from elsworth, for calculating the loss from SLC (really weirdly, should probably be done with real values)
    CR = clamp(CR,0,1)

    U = U235SumCrossSection
    M = MacroscopicCrossSections["Moderator"]["C12"]["Capture"]
    P = 0
    CR = (MacroscopicCrossSections["Absorbers"]["B10"]["Capture"]*(CR*10))
	

    ThermalUtilizationFactor = (U)/(U+M+P+CR)

    #TODO: What does any of this mean?
    Diameter = 0.375*2.54 # in*2.54 = cm	
    Radius = 0.1875*2.54 # in*2.54 = cm
    Length = 0.625*2.54 # in*2.54 = cm

    def calculateDensityChange(initialDensity, temperature): #thank you goosey for making this part easy to understand
        # Constants for UO2
        coefficient = 0.000012 # Linear thermal expansion coefficient (/°C)
        # Calculate the density change
        densityChange = initialDensity * coefficient * temperature
        # Calculate the final density
        finalDensity = initialDensity - densityChange
        # Return the final density
        return finalDensity

    UraniumDensity = calculateDensityChange(10.97, temperatureFuel+273.15) # g/cm for UO2
    pD = UraniumDensity * Diameter
    iEff = 4.45 + 26.6 * math.sqrt(4/pD)

    waterMass = max(230458.9374,waterMass) #Apparently limits to TAF. Do we need this?
	
    #waterMass = waterMass/473072
    waterMass = waterMass/2000

    Nf = 10
    Nm = (40**waterMass)
    Vf = math.pi*Radius*Length

    Lethargy = 0.3
    ScatterCrossSectionModerator = (MicroscopicCrossSections["Moderator"]["H2"]["Thermal"]["Scattering"])/(2.54)

    ResonanceEscapeProbability = math.exp(-((Vf*Nf)/(Lethargy*ScatterCrossSectionModerator*Nm*256.51465299715823))*iEff)

    FastFissionFactor = (1-(1-ResonanceEscapeProbability) * (0.025*2.43*0.93)/(ThermalUtilizationFactor*2.43))

    Width = 3
    Length = 5
    k = 0.2*(10**1) # width/length obtained from buckling graph for reactors
    GeometricBuckling = (k*math.pi/Length)
    FastNonLeakageProbability = 1/(1+(0.02*GeometricBuckling**2))

    DiffusionCoefficient = 0.7
    SigmaA = 70
    Ld = math.sqrt(DiffusionCoefficient/SigmaA)

    ThermalNonLeakageProbability = (1/(1+(Ld**2)+(GeometricBuckling**2)))*2.55

    kEff = ReproductionFactor*ThermalUtilizationFactor*ResonanceEscapeProbability*FastFissionFactor*FastNonLeakageProbability*ThermalNonLeakageProbability

    kStep = (kEff)**0.03
  
    return {"kStep" : kStep, "MacroU235" : MacroscopicU235, "kEff" : kEff}


