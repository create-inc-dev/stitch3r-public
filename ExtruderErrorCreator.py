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

