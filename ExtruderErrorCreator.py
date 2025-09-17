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
        if ("type" in obj.keys() and obj["type"] == Keywords.meshObject):
            toss = coin.toss(probability)
            if toss:
                obj.select_set(True)


def applyGeoNodesPerObject(obj):

    for i in range(len(obj.data.materials)):
        ng = bpy.data.node_groups[Keywords.geoNodesName]
        modifier = obj.modifiers.new(Keywords.geoNodesModifierName, "NODES")
        modifier.node_group = ng
        modifier["Input_4"] = obj.data.materials[i]
        modifier["Socket_0"] = obj.data["layerNumber"]


def applyGeoNodes():
    for obj in bpy.context.selected_objects:
        applyGeoNodesPerObject(obj)
