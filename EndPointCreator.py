import bpy
import math
import sys

moduleParentName = '.'.join(__name__.split('.')[:-1])
ImproperCruveException = sys.modules[moduleParentName + '.Exceptions'].ImproperCruveException
ParamNames = sys.modules[moduleParentName + '.Constants'].ParamNames
Keywords = sys.modules[moduleParentName + '.Constants'].Keywords

def createEndPoint(curveOB, bevelShape): ##End point rounding

    endPointBevel = bevelShape.copy()
    endPointBevel.name = curveOB.name + "_end_point"

    endPointBevel.modifiers.new('Screw', 'SCREW')
    endPointBevel.modifiers.get("Screw").angle = math.pi
    endPointBevel.modifiers.get("Screw").axis = 'Y'

    endPointBevel.rotation_euler[0] = math.pi/2
    endPointBevel.location = (0,0,0)

    endPointBevel.constraints.new("FOLLOW_PATH")
   

    endPointBevel.constraints.get("Follow Path").target = curveOB
    endPointBevel.constraints.get("Follow Path").use_fixed_location = True
    endPointBevel.constraints.get("Follow Path").use_curve_radius = True
    endPointBevel.constraints.get("Follow Path").use_curve_follow = True

    driver = endPointBevel.constraints.get("Follow Path").driver_add("offset_factor").driver

    var = driver.variables.new()
    var.name = "var"
    var.targets[0].id = curveOB
    var.targets[0].data_path = "data.bevel_factor_end"

    driver.expression = var.name

    return endPointBevel

def createStartPoint(curveOB, bevelShape): ##Start point rounding
    startPointBevel = bevelShape.copy()
    startPointBevel.name = curveOB.name + "_start_point"

    startPointBevel.modifiers.new('Screw', 'SCREW')
    startPointBevel.modifiers.get("Screw").angle = math.pi
    startPointBevel.modifiers.get("Screw").axis = 'Y'

    startPointBevel.rotation_euler[0] = math.pi/2
    startPointBevel.location = (0,0,0)

    startPointBevel.constraints.new("FOLLOW_PATH")
   

    startPointBevel.constraints.get("Follow Path").target = curveOB
    startPointBevel.constraints.get("Follow Path").use_fixed_location = True
    startPointBevel.constraints.get("Follow Path").use_curve_radius = True
    startPointBevel.constraints.get("Follow Path").use_curve_follow = True

    driver = startPointBevel.constraints.get("Follow Path").driver_add("offset_factor").driver

    var = driver.variables.new()
    var.name = "var"
    var.targets[0].id = curveOB
    var.targets[0].data_path = "data.bevel_factor_start"

    driver.expression = var.name

    return startPointBevel

def createEndPoints(curveOB, params, coin, seamDistanceProp = "Stitcher_Props.SeamDistance"):
    
    headProb = params[ParamNames.seamAbberations][ParamNames.probability]
    abbAmount = params[ParamNames.seamAbberations][ParamNames.amount]

    bevelShape = curveOB.data.bevel_object
    if (bevelShape == None):
        raise ImproperCruveException(curveOB)

    
    endPointBevel = createEndPoint(curveOB, bevelShape)
    startPointBevel = createStartPoint(curveOB, bevelShape)
    
    mat = bpy.data.materials.get(Keywords.materialName)
    
    if (len(endPointBevel.data.materials) == 0):
        endPointBevel.data.materials.append(mat)
    if (len(startPointBevel.data.materials) == 0):
        startPointBevel.data.materials.append(mat)
    
    try:
        curveOB.data["lengthOfCurve"]
        endPointBevel["layerNumber"] = startPointBevel["layerNumber"] = curveOB["layerNumber"]
        endPointBevel["type"] = startPointBevel["type"] = "End_Point"
        endPointBevel["parent"] = startPointBevel["parent"] = curveOB

    except KeyError:
        raise ImproperCruveException(curveOB)

    curveOB.data["startOffset"] = 0.00
    curveOB.data["endOffset"] = 0.00


    ##Make start and end offset absolute according to length, so that the seams can be managed from a central value using offset
    driver = curveOB.data.driver_add("bevel_factor_start").driver
    
    var0 = driver.variables.new()
    var0.name = "var1"
    var0.targets[0].id = curveOB
    var0.targets[0].data_path = 'data["startOffset"]'

    var1 = driver.variables.new()
    var1.name = "var2"
    var1.targets[0].id_type = curveOB.type
    var1.targets[0].id = curveOB.data
    var1.targets[0].data_path = '["lengthOfCurve"]'

    if (coin.toss(headProb)):
        driver.expression = "(1 - ({1} - ({0} + {2}))/{1}) ".format(var0.name, var1.name, coin.uniform(0,abbAmount))
    else:
        driver.expression = "(1 - ({1} - {0})/{1})".format(var0.name, var1.name)


    driver = curveOB.data.driver_add("bevel_factor_end").driver
    
    var0 = driver.variables.new()
    var0.name = "var1"
    var0.targets[0].id = curveOB
    var0.targets[0].data_path = 'data["endOffset"]'

    var1 = driver.variables.new()
    var1.name = "var2"
    var1.targets[0].id_type = curveOB.type
    var1.targets[0].id = curveOB.data
    var1.targets[0].data_path = '["lengthOfCurve"]'
    
    if (coin.toss(headProb)):
        driver.expression = "(({1} - ({0} + {2}))/{1}) ".format(var0.name, var1.name, coin.uniform(0,abbAmount))
    else:
        driver.expression = "({1} - {0})/{1}".format(var0.name, var1.name)


    ##Linking everything to the seam distance slider on the addon
    driver = curveOB.data.driver_add('["endOffset"]').driver
    var = driver.variables.new()
    var.name = "var"
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = bpy.context.scene
    var.targets[0].data_path =  seamDistanceProp 
    driver.expression = var.name

    driver = curveOB.data.driver_add('["startOffset"]').driver
    var = driver.variables.new()
    var.name = "var"
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = bpy.context.scene
    var.targets[0].data_path =  seamDistanceProp 
    driver.expression = var.name

    return (endPointBevel, startPointBevel)


if __name__ == "__main__":
    endPoint, startPoint = createEndPoints(bpy.data.objects.get("myCurve"))
    bpy.data.collections.get("Layer 1").objects.link(endPoint)
    bpy.data.collections.get("Layer 1").objects.link(startPoint)

