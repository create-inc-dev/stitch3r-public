from random import Random, randint
import re


class ParamNames:
    widthOffset = "WidthOffset"
    heightOffset = "HeightOffset"
    precision = "Precision"
    seamAbberations = "Seam Abberations"
    seamDistance = "SeamDistance"
    mergeAngle = "MergeAngle"
    SlicesPerPrintLine = "SlicesPerPrintLine"
    degreesPerJointPoint = "DegreesPerJointPoint"

    amount = "Amount"
    probability = "Probability"

    seed = "Seed"


class Keywords:
    layerNumber = "layerNumber"
    materialName = "Stitcher Material"
    geoNodesName = "Stitcher Geometry Nodes"
    importCollectionName = "Import Things"
    shadowCatcherCollectionName = "Shadow Catcher"
    geoNodesModifierName = "GeoNodes"
    viewportOnly = "ViewportOnly"
    parent = "parent"
    featureType = "type"
    zPos = "zPos"
    startPoint = "startPoint"
    endPoint = "endPoint"
    meshObject = "meshObject"


class Patterns:
    # Pattern that matches G0 or G1 commands. To be noted, I don't see any G0 commansd in Prusa Slicer.
    gcodePattern = re.compile(
        "(\s*G[01](?:\s+[XYZEF](?:[-+]?(?:\d*\.\d+|\d+)))+\s*)(?:;(.*))?$")
    # Matches the G0 or G1 commands that have no X,Y or Z components, thereby are not travel moves.
    nonMovingGcodePattern = re.compile(
        "\s*G[01](\s+[EF](?:[-+]?(?:\d*\.\d+|\d+)))+\s*$")
    filamentChangePattern = re.compile("\s*T(\d+)$")
    curveGcodePattern = re.compile(
        "(\s*G([23])(?:\s+[XYZEFPIJR](?:[-+]?(?:\d*\.\d+|\d+)))+\s*)(?:;(.*))?$")

    printerSpecificPatterns = {'orca': {
        'layerChangePattern': re.compile("\s*;LAYER_CHANGE\s*"),
        # Detecting a change in the width of print line
        'widthPattern': re.compile("\s*;WIDTH:([0-9]+(?:\.[0-9]+)?)\s*$"),
        'zPosPattern': re.compile("\s*;Z:([0-9]+(?:\.[0-9]+)?)\s*$"),
        'heightPattern': re.compile("\s*;HEIGHT:([0-9]+(?:\.[0-9]+)?)\s*$"),
        'typePattern': re.compile("\s*;TYPE:(.*)$"),
        'filamentChangePattern': re.compile("\s*T(\d+)$")
    }}


class Types:
    externalPerimeter = "External_perimeter"
    extruderError = "Extruder_Error"
    endPoint = "End_Point"


class BiasedCoin:
    def __init__(self, seed=randint(0, 500)):
        self.randGenerator = Random()
        self.randGenerator.seed = seed

    def toss(self, headProb):
        weights = [100-headProb, headProb]
        return self.randGenerator.choices([0, 1], weights=weights)[0]

    def uniform(self, a, b):
        return self.randGenerator.uniform(a, b)


objectProperties = [Keywords.layerNumber, Keywords.parent,
                    Keywords.featureType, Keywords.zPos, Keywords.startPoint, Keywords.endPoint]


def getFilamentName(filamentPrefix, number):
    return filamentPrefix + "_" + str(number)


propsNonAnimatable = ['WidthOffset', 'HeightOffset', 'SeamDistance', 'MergeAngle', 'SlicesPerPrintLine', 'DegreesPerJointPoint', ('Seam Abberations', (
    'SeamAbberation_Amount', 'Amount'), ('SeamAbberation_Probability', 'Probability')), ]
