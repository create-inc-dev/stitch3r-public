import bpy
import sys
moduleParentName = '.'.join(__name__.split('.')[:-1])
Coin = sys.modules[moduleParentName + '.Constants'].BiasedCoin
Types = sys.modules[moduleParentName + '.Constants'].Types
Keywords = sys.modules[moduleParentName + '.Constants'].Keywords

def makeSelection(collection, probability, seed):
    coin = Coin()

    for obj in bpy.context.selected_objects:
        obj.select_set(False)

    for obj in collection.all_objects:
        if (obj["type"] == Types.externalPerimeter):
            toss = coin.toss(probability)
            if toss:
                obj.select_set(True)

def applyGeoNodesPerObject(obj):
    
    ng = bpy.data.node_groups[Keywords.geoNodesName]
    modifier = obj.modifiers.new(Keywords.geoNodesModifierName, "NODES")
    bpy.data.node_groups.remove(modifier.node_group)
    modifier.node_group = ng

    if (len(obj.data.materials) != 0):
        modifier["Input_4"] =  obj.data.materials[0]

    driver = obj.driver_add('modifiers["{}"]["Input_2"]'.format(Keywords.geoNodesModifierName)).driver
    var = driver.variables.new()
    var.name = "var"
    var.targets[0].id_type = 'SCENE'
    var.targets[0].id = bpy.context.scene
    var.targets[0].data_path =  "Stitcher_Props.ExtruderError_Density" 
    driver.expression = var.name

    bevelShape = obj.data.bevel_object

    driver = obj.driver_add('modifiers["{}"]["Input_3"]'.format(Keywords.geoNodesModifierName)).driver
    var = driver.variables.new()
    var.name = "var"
    var.targets[0].id_type = bevelShape.type
    var.targets[0].id = bevelShape.data
    var.targets[0].data_path =  '["height"]'
    driver.expression = var.name

    driver = obj.driver_add('modifiers["{}"].show_viewport'.format(Keywords.geoNodesModifierName)).driver
    
    var1 = driver.variables.new()
    var1.name = "var1"
    var1.targets[0].id_type = 'SCENE'
    var1.targets[0].id = bpy.context.scene
    var1.targets[0].data_path = "Stitcher_Props." + Types.extruderError
    driver.expression = var1.name

    driver = obj.driver_add('modifiers["{}"].show_render'.format(Keywords.geoNodesModifierName)).driver

    var1 = driver.variables.new()
    var1.name = "var1"
    var1.targets[0].id_type = 'SCENE'
    var1.targets[0].id = bpy.context.scene
    var1.targets[0].data_path = "Stitcher_Props." + Types.extruderError

    var2 = driver.variables.new()
    var2.name = "var2"
    var2.targets[0].id_type = 'SCENE'
    var2.targets[0].id = bpy.context.scene
    var2.targets[0].data_path = "Stitcher_Props." + Keywords.viewportOnly
    driver.expression = "{0} or {1}".format(var1.name, var2.name)
    
def applyGeoNodes():
    for obj in bpy.context.selected_objects:
        applyGeoNodesPerObject(obj)
