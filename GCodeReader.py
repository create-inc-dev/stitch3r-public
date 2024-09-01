from ast import Param
import bpy
import sys
import math
import re
from itertools import tee
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_line_2d, intersect_line_line

from numpy import number, var


moduleParentName = '.'.join(__name__.split('.')[:-1])
createProfile = sys.modules[moduleParentName +
                            '.BevelShapeCreator'].createProfile
NoZPosMatch = sys.modules[moduleParentName + '.Exceptions'].NoZPosMatch
NoHeightMatch = sys.modules[moduleParentName + '.Exceptions'].NoHeightMatch
NoSuchPropertyException = sys.modules[moduleParentName +
                                      '.Exceptions'].NoSuchPropertyException
createEndPoints = sys.modules[moduleParentName +
                              '.EndPointCreator'].createEndPoints
ImproperCruveException = sys.modules[moduleParentName +
                                     '.Exceptions'].ImproperCruveException

ParamNames = sys.modules[moduleParentName + '.Constants'].ParamNames
Coin = sys.modules[moduleParentName + '.Constants'].BiasedCoin
Keywords = sys.modules[moduleParentName + '.Constants'].Keywords


class Layer:  # Class that stores information about the layer. Needs to change because there are different widths in the same layer as well
    def __init__(self, zPos, height, layerNumber, gcodes) -> None:
        self.zPos = zPos
        self.layerNumber = layerNumber
        self.height = height
        self.gcodes = gcodes

    def __str__(self) -> str:
        return "zPos:{0} | height:{1} | {2}".format(self.zPos, self.height, self.gcodes)


# Reads the GCode Files, extracts only the G1 and G0 moves. Sorry no support for circular moves so far.
def gcodeParser(gcodeFilePath, params):

    print(__file__)
    file = open(gcodeFilePath, 'r')
    lines = file.readlines()
    numberOfLines = len(lines)
    linesIterator = iter(lines)
    listOfParsedLayers = []

    # Pattern that matches G0 or G1 commands. To be noted, I don't see any G0 commansd in Prusa Slicer.
    gcodePattern = re.compile(
        "(\s*G[01](?:\s+[XYZEF](?:[-+]?(?:\d*\.\d+|\d+)))+\s*)(?:;(.*))?$")
    # Matches the G0 or G1 commands that have no X,Y or Z components, thereby are not travel moves.
    nonMovingGcodePattern = re.compile(
        "\s*G[01](\s+[EF](?:[-+]?(?:\d*\.\d+|\d+)))+\s*$")
    # Detecting Layer change, I think this makes things incompatible with vase mode.
    layerChangePattern = re.compile("\s*;LAYER_CHANGE\s*")
    # Detecting a change in the width of print line
    widthPattern = re.compile("\s*;WIDTH:([0-9]+(?:\.[0-9]+)?)\s*$")
    zPosPattern = re.compile("\s*;Z:([0-9]+(?:\.[0-9]+)?)\s*$")
    heightPattern = re.compile("\s*;HEIGHT:([0-9]+(?:\.[0-9]+)?)\s*$")
    typePattern = re.compile("\s*;TYPE:(.*)$")
    firstPointPattern = re.compile("move to first")

    prevLayerGcodes = []  # All GCodes that move the nozzle, with our without extrusion would be stored here and then popped when the next later starts
    # Prusa Slicer Prints the Z position and layer height after each layer change
    prevLayerZPos = 0
    prevLayerHeight = 0
    curLineNumber = 0  # For error tracing
    curLayerNumber = 0

    # E is extrusion; X, Y and Z are the coordinates; W is width of the  print line
    valueTacker = {'X': 0, 'Y': 0, 'Z': 0, 'E': 0, 'W': 0.5,
                   'H': 0.2, 'layerNumber': 0, 'type': 'Custom'}

    whPrecision = params[ParamNames.whPrecision]
    precision = params[ParamNames.precision]

    while True:
        try:
            line = next(linesIterator)
        except StopIteration:
            line = "!__end__!"

        curLineNumber = curLineNumber + 1

        if bool(gcodePattern.match(line)):

            gcodePart = gcodePattern.search(line)[1].strip()
            """commentPart = "" ##Only needed if there is a need to process comments later

            try:
                commentPart = gcodePattern.search(line)[2].strip()
            except (IndexError, AttributeError):
                pass"""

            separatedGcode = gcodePart.split()
            tempDict = valueTacker.copy()

            # Ignore any GCode G0/G1 command that doesn't move the extruder
            if not bool(nonMovingGcodePattern.match(gcodePart)):

                for term in separatedGcode:
                    tempDict[term[0]] = float(term[1:])
                    if term[0] in ['X', 'Y', 'Z']:
                        valueTacker[term[0]] = round(
                            float(term[1:]), precision)
                tempDict['lineNumber'] = curLineNumber

                prevLayerGcodes.append(tempDict.copy())

        # In case of layer change, push the accumulated GCodes of previous layer and start accumulating the next one.
        elif bool(layerChangePattern.match(line)):
            zPos = 0
            height = 0

            try:
                line = next(linesIterator)
                curLineNumber = curLineNumber + 1
                zPos = float(zPosPattern.search(line)[1])
            except (IndexError, TypeError):
                raise NoZPosMatch(line, curLineNumber)

            try:
                line = next(linesIterator)
                curLineNumber = curLineNumber + 1
                height = round(
                    float(heightPattern.search(line)[1]), whPrecision)
                valueTacker['H'] = height

            except (IndexError, TypeError):
                raise NoHeightMatch(line, curLineNumber)

            prevLayer = Layer(prevLayerZPos, prevLayerHeight,
                              curLayerNumber, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)

            prevLayerGcodes = []
            prevLayerZPos = zPos
            prevLayerHeight = height
            curLayerNumber = curLayerNumber + 1

        elif bool(heightPattern.match(line)):
            valueTacker['H'] = round(
                float(heightPattern.search(line)[1]), whPrecision)

        elif bool(widthPattern.match(line)):
            valueTacker['W'] = round(
                float(widthPattern.search(line)[1]), whPrecision)

        elif bool(typePattern.match(line)):
            curveType = typePattern.search(line)[1].strip()
            valueTacker['type'] = re.sub(" |/", "_", curveType)

        elif line == "!__end__!":
            prevLayer = Layer(prevLayerZPos, prevLayerHeight,
                              curLayerNumber, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)
            break

        else:
            pass

    return listOfParsedLayers


def addVisibilityDriver(curveOB, drivenProperty="hide_viewport"):
    try:
        curveType = curveOB["type"]
    except KeyError:
        raise ImproperCruveException(curveOB)

    driver = curveOB.driver_add(drivenProperty).driver
    var0 = driver.variables.new()
    var0.name = "var0"
    var0.targets[0].id_type = 'SCENE'
    var0.targets[0].id = bpy.context.scene
    var0.targets[0].data_path = "Stitcher_Props.LayerIndexTop"

    var1 = driver.variables.new()
    var1.name = "var1"
    var1.targets[0].id_type = 'SCENE'
    var1.targets[0].id = bpy.context.scene

    filter_index = bpy.context.scene.Stitcher_Props.TypesFiltersDict[curveType]
    var1.targets[0].data_path = "Stitcher_Props.TypesFiltersMap[{" + \
        filter_index + "}].value"

    var2 = driver.variables.new()
    var2.name = "var2"
    var2.targets[0].id = curveOB
    var2.targets[0].data_path = '["layerNumber"]'

    condition1 = var1.name  # is the curve type checked in the visibility tab
    # is the layer supposed to be visible i.e. layer number <= layer top index
    condition2 = "({0} <= {1})".format(var2.name, var0.name)
    condition3 = "True"  # is the parent visible

    if (drivenProperty == "hide_render"):
        var4 = driver.variables.new()
        var4.name = "var4"
        var4.targets[0].id_type = 'SCENE'
        var4.targets[0].id = bpy.context.scene
        var4.targets[0].data_path = "Stitcher_Props.ViewportOnly"

        condition1 = "({0} or {1})".format(var1.name, var4.name)

    # The rounded starting and end points would have a parent parameter that points to the curve they are placed on.
    # It's import to tie their visbility to their parent
    if ('parent' in curveOB.keys()):
        var3 = driver.variables.new()
        var3.name = "var3"
        var3.targets[0].id = curveOB['parent']
        var3.targets[0].data_path = drivenProperty

        condition3 = "not (" + var3.name + ")"

    driver.expression = "not ({0} and {1} and {2})".format(
        condition1, condition2, condition3)


# Apply modifier to smooth out overlap artefacts, only shows in renders
def addEnhancingModifiers(curveOB):
    curveOB.modifiers.new('split', 'EDGE_SPLIT')
    curveOB.modifiers.get('split').show_viewport = False


def triplewise(iterable):
    "triplewise('ABCDEFG') --> ABC BCD CDE DEF EFG"
    # Create three iterators
    a, b, c = tee(iterable, 3)
    # Advance iterators to create the sliding window
    next(b, None)
    next(c, None)
    next(c, None)
    # Zip the iterators together
    return zip(a, b, c)


def getInsetCurve(coords):
    coordinateBuffer = []
    innerCurveCoordinates = []

    i = 0

    zAxisVector = Vector((0, 0, 1))

    while i < len(coords):
        coordinateBuffer.append(coords[i])
        if len(coordinateBuffer) > 3:
            coordinateBuffer.pop(0)

        if len(coordinateBuffer) == 3:
            coord1, coord2, coord3 = (
                coordinateBuffer[0], coordinateBuffer[1], coordinateBuffer[2])

            firstVector = Vector(coord2["point"]) - Vector(coord1["point"])
            secondVector = Vector(coord3["point"]) - Vector(coord2["point"])

            firstNormal = firstVector.cross(zAxisVector).normalized()
            secondNormal = secondVector.cross(zAxisVector).normalized()

            firstOffset = firstNormal * coord2["width"]/2
            secondOffset = secondNormal * coord2["width"]/2

        i += 1


def isInnerOffset(firstVector, secondVector):
    return True if firstVector.cross(secondVector).z < 0 else False


def getOffsetCurves(coords, jointResolution):
    outerCurveCoordinates = []
    offset1CurveCoordinates = []

    zAxisVector = Vector((0, 0, 1))

    coordinateBuffer = []

    i = 0
    while i < len(coords):
        coordinateBuffer.append(coords[i])
        if len(coordinateBuffer) > 3:
            coordinateBuffer.pop(0)

        if len(coordinateBuffer) == 3:
            coord1, coord2, coord3 = (
                coordinateBuffer[0], coordinateBuffer[1], coordinateBuffer[2])

            point1, point2, point3 = (
                Vector(coord1["point"]), Vector(coord2["point"]), Vector(coord3["point"]))

            firstOffset = coord2["width"]/2
            secondOffset = coord3["width"]/2

            firstVector = point2 - point1
            secondVector = point3 - point2

            firstNormal = firstVector.cross(zAxisVector).normalized()
            secondNormal = secondVector.cross(zAxisVector).normalized()

            firstOffsetVector = firstNormal * firstOffset
            secondOffsetVector = secondNormal * secondOffset

            offset1Edge1StartPoint, offset1Edge1EndPoint, offset1Edge2StartPoint, offset1Edge2EndPoint = (
                point1 + firstOffsetVector, point2 + firstOffsetVector, point2 + secondOffsetVector, point3 + secondOffsetVector)

            offset2Edge1StartPoint, offset2Edge1EndPoint, offset2Edge2StartPoint, offset2Edge2EndPoint = (
                point1 - firstOffsetVector, point2 - firstOffsetVector, point2 - secondOffsetVector, point3 - secondOffsetVector)

            if i == 2:
                offset1CurveCoordinates.append(offset1Edge1StartPoint)

            innerOffset = "offset1" if isInnerOffset(
                firstVector, secondVector) else "offset2"

            if innerOffset == "offset1":
                innerOffsetPoints = [
                    offset1Edge1StartPoint, offset1Edge1EndPoint, offset1Edge2StartPoint, offset1Edge2EndPoint]
                outerOffsetPoints = [
                    offset2Edge1StartPoint, offset2Edge1EndPoint, offset2Edge2StartPoint, offset2Edge2EndPoint]

                outerOffsetMultiplier = -1

            else:
                innerOffsetPoints = [
                    offset2Edge1StartPoint, offset2Edge1EndPoint, offset2Edge2StartPoint, offset2Edge2EndPoint]
                outerOffsetPoints = [
                    offset1Edge1StartPoint, offset1Edge1EndPoint, offset1Edge2StartPoint, offset1Edge2EndPoint]

                outerOffsetMultiplier = 1

            angleBetween = firstNormal.angle(secondNormal)
            angleBetween = angleBetween if angleBetween < math.pi else math.pi * 2 - angleBetween

            numberOfPoints = angleBetween // (36 * math.pi / 180)

            outerOffsetIntersections = []

            for j in range(int(numberOfPoints)):
                pointWidth = (j + 1)/(numberOfPoints + 1) * firstOffset + \
                    (1 - (j + 1)/(numberOfPoints + 1)) * \
                    secondOffset
                rotationMatrix = Matrix.Rotation(
                    (j + 1)/(numberOfPoints + 1) * outerOffsetMultiplier * angleBetween, 4, 'Z')
                displacementVector = (
                    outerOffsetMultiplier * firstNormal).to_3d()
                displacementVector.rotate(rotationMatrix)
                outerOffsetIntersections.append(Vector(
                    coord2["point"]) + displacementVector * pointWidth)

            previousInnerCurveCoordinate = offset1CurveCoordinates[-1]

            innerOffsetSelected = intersect_line_line_2d(
                previousInnerCurveCoordinate, outerOffsetPoints[1], point1, point2) != None or intersect_line_line_2d(
                previousInnerCurveCoordinate, outerOffsetPoints[2], point2, point3) != None or intersect_line_line_2d(
                previousInnerCurveCoordinate, outerOffsetPoints[1], point2, point3) != None or intersect_line_line_2d(
                previousInnerCurveCoordinate, outerOffsetPoints[2], point1, point2) != None

            if innerOffsetSelected:
                innerOffsetIntersection = intersect_line_line_2d(
                    innerOffsetPoints[0], innerOffsetPoints[1], innerOffsetPoints[2], innerOffsetPoints[3])

                if not innerOffsetIntersection:
                    if angleBetween < math.pi/2:
                        innerOffsetIntersection = (
                            innerOffsetPoints[1] + innerOffsetPoints[2])/2
                        offset1CurveCoordinates.append(innerOffsetIntersection)

                    elif firstVector.length/firstOffset < secondVector.length/secondOffset:
                        coordinateBuffer.pop(1)

                    else:
                        coordinateBuffer.pop(2)

                else:
                    innerOffsetIntersection = innerOffsetIntersection.to_3d()
                    innerOffsetIntersection.z = (innerOffsetPoints[1].z +
                                                 innerOffsetPoints[2].z) / 2
                    offset1CurveCoordinates.append(innerOffsetIntersection)

                if i == len(coords) - 1:
                    offset1CurveCoordinates.append(innerOffsetPoints[3])

            else:
                if len(outerOffsetIntersections) > 0:
                    offset1CurveCoordinates.append(outerOffsetPoints[1])
                    offset1CurveCoordinates.extend(outerOffsetIntersections)
                    offset1CurveCoordinates.append(outerOffsetPoints[2])
                else:
                    outerOffsetIntersection = (
                        outerOffsetPoints[1] + outerOffsetPoints[2])/2
                    offset1CurveCoordinates.append(outerOffsetIntersection)

                if i == len(coords) - 1:
                    offset1CurveCoordinates.append(outerOffsetPoints[3])

        i += 1

    return {"outer": outerCurveCoordinates, "inner": offset1CurveCoordinates}


def placeLayer(curves, zPos, layerNumber, collection, params):
    widthOffset = params[ParamNames.widthOffset]
    heightOffset = params[ParamNames.heightOffset]
    whPrecision = params[ParamNames.whPrecision]

    lengthOfCurve = 0

    offset1CurveData = bpy.data.curves.new('myCurve', type='CURVE')
    offset1CurveData.dimensions = '3D'
    offset1CurveData.resolution_u = 1
    offset1CurveData.render_resolution_u = 12

    mainCurveData = bpy.data.curves.new('myCurve', type='CURVE')
    mainCurveData.dimensions = '3D'
    mainCurveData.resolution_u = 1
    mainCurveData.render_resolution_u = 12

    offset2CurveData = bpy.data.curves.new('myCurve', type='CURVE')
    offset2CurveData.dimensions = '3D'
    offset2CurveData.resolution_u = 1
    offset2CurveData.render_resolution_u = 12

    for curve in curves:
        coords = curve['coords']

        visibilityPropertyIndex = bpy.context.scene.Stitcher_Props.TypesFiltersDict[
            curve['type']]
        isTypeVisible = bpy.context.scene.Stitcher_Props.TypesFiltersMap[
            visibilityPropertyIndex].value

        if (len(coords) > 1 and isTypeVisible):
            offsetCurves = getOffsetCurves(coords, 1)
            polyline = offset1CurveData.splines.new('POLY')
            polyline.points.add(len(offsetCurves["outer"]) - 1)

            for idx, coord in enumerate(offsetCurves["outer"]):
                x, y, z = coord
                polyline.points[idx].co = (x, y, z, 1)

            polyline = offset2CurveData.splines.new('POLY')
            polyline.points.add(len(offsetCurves["inner"]) - 1)

            for idx, coord in enumerate(offsetCurves["inner"]):
                x, y, z = coord
                polyline.points[idx].co = (x, y, z, 1)

            polyline = mainCurveData.splines.new('POLY')
            polyline.points.add(len(coords) - 1)

            for idx, coord in enumerate(coords):
                x, y, z = coord["point"]
                polyline.points[idx].co = (x, y, z, 1)

    offset1CurveOB = bpy.data.objects.new(
        f'Layer_{layerNumber}', offset1CurveData)
    offset2CurveOB = bpy.data.objects.new(
        f'Layer_{layerNumber}', offset2CurveData)
    mainCurveOB = bpy.data.objects.new(
        f'Layer_Main_{layerNumber}', mainCurveData)

    # Properties for debugging and other uses
    offset1CurveOB.data["zPos"] = zPos
    offset1CurveOB["zPos"] = zPos

    # curveOB.data["type"] = curveType
    # curveOB["type"] = curveType

    offset1CurveOB.data["lengthOfCurve"] = lengthOfCurve

    offset1CurveOB.data["layerNumber"] = layerNumber
    offset1CurveOB["layerNumber"] = layerNumber

    collection.objects.link(offset1CurveOB)
    collection.objects.link(mainCurveOB)
    collection.objects.link(offset2CurveOB)

    return offset1CurveOB


# Take the parsed GCode and finally make it into a curve that is beveled on blender
def placeCurve(coords, width, height, zPos, curveType, layerNumber, bevelSuffix, collection, params):

    widthOffset = params[ParamNames.widthOffset]
    heightOffset = params[ParamNames.heightOffset]
    whPrecision = params[ParamNames.whPrecision]

    lengthOfCurve = 0

    if (len(coords) > 1):

        # Create new curve data and set it's properties
        # Dimensions are set to 3D because setting it to 2D produces weird bugs and artefacts
        curveData = bpy.data.curves.new('myCurve', type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 1
        curveData.render_resolution_u = 12

        # It's not a polyline curve, it's a bezier curve being edited to emulate a polyline curve.
        # A polyline curve was giving uneven thickness when beveled
        polyline = curveData.splines.new('BEZIER')

        bevelObject = None
        prevCoord = coords[0]

        x, y, z = prevCoord
        polyline.bezier_points[0].co = (x, y, z)
        polyline.bezier_points[0].handle_left = (x, y, z)
        polyline.bezier_points[0].handle_right = (x, y, z)

        for i, coord in enumerate(coords[1:]):

            distFromPreviousCoord = math.dist(prevCoord, coord)

            if (distFromPreviousCoord > 0):
                polyline.bezier_points.add(1)
                lengthOfCurve = lengthOfCurve + distFromPreviousCoord
                x, y, z = coord

                polyline.bezier_points[-1].co = (x, y, z)
                polyline.bezier_points[-1].handle_left = (x, y, z)
                polyline.bezier_points[-1].handle_right = (x, y, z)

                prevCoord = coord

        if lengthOfCurve == 0:
            return None

        curveOB = bpy.data.objects.new('myCurve', curveData)

        # Properties for debugging and other uses
        curveOB.data["zPos"] = zPos
        curveOB["zPos"] = zPos

        curveOB.data["type"] = curveType
        curveOB["type"] = curveType

        curveOB.data["lengthOfCurve"] = lengthOfCurve

        curveOB.data["layerNumber"] = layerNumber
        curveOB["layerNumber"] = layerNumber
        curveOB.hide_viewport = True

        bevelName = ("{:."+str(whPrecision)+"f}").format(width + widthOffset) + "_" + (
            "{:."+str(whPrecision)+"f}").format(height + heightOffset) + "_" + bevelSuffix

        if bevelName in bpy.data.objects.keys():
            bevelObject = bpy.data.objects.get(bevelName)
        else:
            createProfile(width+widthOffset, height+heightOffset, 1, bevelName)
            bevelObject = bpy.data.objects.get(bevelName)

        curveData.bevel_mode = "OBJECT"
        curveData.bevel_object = bpy.data.objects.get(bevelName)
        curveData.use_fill_caps = True

        # Material was already imported from assets.blend file when the "Load GCode" button was pressed
        mat = bpy.data.materials.get(Keywords.materialName)
        if (len(curveOB.data.materials) == 0):
            curveOB.data.materials.append(mat)

        addEnhancingModifiers(curveOB)

        # Change bevel mapping - this would be used for rounding the end points of the curve
        curveOB.data.bevel_factor_mapping_start = 'SPLINE'
        curveOB.data.bevel_factor_mapping_end = 'SPLINE'

        collection.objects.link(curveOB)

        return curveOB


def builder(gcodeFilePath, objectName="OBJECT", bevelSuffix="bevel", params={}):

    # print(params)
    coin = Coin(params[ParamNames.seed])

    listOfParsedLayers = gcodeParser(gcodeFilePath, params)

    i = 0

    parentCollection = bpy.data.collections.new(objectName)
    bpy.context.scene.collection.children.link(parentCollection)

    numberOfLayers = len(listOfParsedLayers) - 1
    for currentLayer in listOfParsedLayers:

        prevWidth = 0
        prevType = "Custom"
        prevHeight = 0
        coords = []

        layerCollection = bpy.data.collections.new(
            "Layer " + str(currentLayer.layerNumber))
        parentCollection.children.link(layerCollection)

        # Below line is used for debugging particular lines of gcode
        # currentLayer.gcodes = filter(lambda x: 73 < x['lineNumber'] and x['lineNumber'] <= 93 ,currentLayer.gcodes)

        def placeCurveFunc(curveType):

            curveOB = placeCurve(coords, prevWidth, prevHeight, currentLayer.zPos,
                                 prevType, currentLayer.layerNumber, bevelSuffix, layerCollection, params)
            if (not curveOB == None):
                addVisibilityDriver(curveOB, "hide_viewport")
                addVisibilityDriver(curveOB, "hide_render")

            if (curveType in ["External_perimeter", "Skirt_Brim", "Perimeter", "Top_solid_infill", "Overhang_perimeter"] and not curveOB == None):
                endPoint, startPoint = createEndPoints(curveOB, params, coin)
                layerCollection.objects.link(endPoint)
                layerCollection.objects.link(startPoint)

                addVisibilityDriver(endPoint, "hide_viewport")
                addVisibilityDriver(startPoint, "hide_viewport")
                addVisibilityDriver(endPoint, "hide_render")
                addVisibilityDriver(startPoint, "hide_render")
                curveOB[Keywords.startPoint] = startPoint
                curveOB[Keywords.endPoint] = startPoint

        for elem in currentLayer.gcodes:
            # print(elem)
            if (elem["E"] > 0):
                if (elem['W'] == prevWidth and elem['type'] == prevType and elem['H'] == prevHeight):
                    coords.append((elem['X'], elem['Y'], elem['Z']))
                else:
                    placeCurveFunc(prevType)

                    prevWidth = elem['W']
                    prevType = elem['type']
                    prevHeight = elem['H']

                    coords = coords[-1:]
                    coords.append((elem['X'], elem['Y'], elem['Z']))

            else:

                placeCurveFunc(prevType)
                coords = [(elem['X'], elem['Y'], elem['Z'])]

        placeCurveFunc(prevType)

        print("Layer Done: {}/{}".format(currentLayer.layerNumber,
              numberOfLayers), end='\r', flush=True)
        i = i + 1
    print("")

    bpy.context.scene["Stitcher_Object_Collection"] = parentCollection
