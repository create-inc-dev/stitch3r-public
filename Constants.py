from random import Random, randint

class ParamNames:
    widthOffset = "WidthOffset"
    heightOffset = "HeightOffset"
    precision = "Precision"
    seamAbberations = "Seam Abberations"

    amount = "Amount"
    probability = "Probability"

    seed = "Seed"

class Keywords:
    layerNumber = "layerNumber"
    materialName = "Stitcher Material"
    geoNodesName = "Stitcher Geometry Nodes"
    importCollectionName = "Import Things"
    geoNodesModifierName = "GeoNodes"
    viewportOnly = "ViewportOnly"
    parent = "parent"
    featureType = "type"
    zPos = "zPos"
    startPoint = "startPoint"
    endPoint = "endPoint"


class Types:
    externalPerimeter = "External_perimeter"
    extruderError = "Extruder_Error"
    endPoint = "End_Point"

class BiasedCoin:
    def __init__(self, seed=randint(0,500)):
        self.randGenerator = Random()
        self.randGenerator.seed = seed

    def toss(self, headProb):
        weights = [100-headProb, headProb]
        return self.randGenerator.choices([0,1], weights=weights)[0]

    def uniform(self,a,b):
        return self.randGenerator.uniform(a,b)

objectProperties = [Keywords.layerNumber, Keywords.parent, Keywords.featureType, Keywords.zPos, Keywords.startPoint, Keywords.endPoint]