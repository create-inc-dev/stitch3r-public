import bpy
import sys
moduleParentName = '.'.join(__name__.split('.')[:-1])
Coin = sys.modules[moduleParentName + '.Constants'].BiasedCoin
Types = sys.modules[moduleParentName + '.Constants'].Types

def makeSelection(collection, probability, seed):
    coin = Coin()

    for obj in bpy.context.selected_objects:
        obj.select_set(False)

    for obj in collection.all_objects:
        if (obj.data.get("type") == Types.externalPerimeter):
            toss = coin.toss(probability)
            if toss:
                obj.select_set(True)

def applyGeoNodes():
    for obj in bpy.context.selected_objects:
        ng = bpy.data.node_groups['Buddy Geometry Nodes']
        modifier = obj.modifiers.new("MyName", "NODES")
        bpy.data.node_groups.remove(modifier.node_group)
        modifier.node_group = ng
    
