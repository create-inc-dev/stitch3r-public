from ast import Param
import bpy
import sys
import math
import re
import bmesh
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


def getSegments(coords, mergeAngle=(180 - 3) * math.pi/180):
    newCoords = []
    coordinateBuffer = []

    segments = []

    currentSegment = []

    i = 0
    while i < len(coords):

        if i == 0:
            newCoords.append(coords[i])
        elif i == len(coords) - 1:
            newCoords.append(coords[i])

        else:
            coord1 = newCoords[-1]
            coord2 = coords[i]
            coord3 = coords[i + 1]

            point1, point2, point3 = (
                Vector(coord1["point"]), Vector(coord2["point"]), Vector(coord3["point"]))

            firstVector = point2 - point1
            secondVector = point3 - point2

            angleBetween = (firstVector * -1).angle(secondVector, math.pi)
            angleBetween = angleBetween if angleBetween < math.pi else math.pi * 2 - angleBetween

            if angleBetween < mergeAngle:
                newCoords.append(coord2)

        i += 1

    i = 0
    while i < len(newCoords):
        coordinateBuffer.append(newCoords[i])
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

            if firstVector.length < secondOffset / abs(math.sin(firstVector.angle(secondVector))):
                if len(currentSegment) > 0:
                    segments.append(currentSegment)
                    currentSegment = []

                segments.append([coord1, coord2])

                if i == len(newCoords) - 1:
                    segments.append([coord2, coord3])

            elif secondVector.length < firstOffset / abs(math.sin(firstVector.angle(secondVector))):
                if len(currentSegment) == 0:
                    currentSegment.append(coord1)

                currentSegment.append(coord2)
                segments.append(currentSegment)
                currentSegment = []

                segments.append([coord2, coord3])

            else:
                if len(currentSegment) == 0:
                    currentSegment.append(coord1)

                currentSegment.append(coord2)

                if i == len(newCoords) - 1:
                    currentSegment.append(coord3)
                    segments.append(currentSegment)

        i += 1

    return segments


def getPointsOnCurve(angleBetweenNormals, numberOfPoints, firstOffset, secondOffset, displacementVector, intersectionPoint):
    resultingPoints = []
    for j in range(numberOfPoints):
        pointWidth = (j + 1)/(numberOfPoints + 1) * firstOffset + \
            (1 - (j + 1)/(numberOfPoints + 1)) * \
            secondOffset
        rotationMatrix = Matrix.Rotation(
            (j + 1)/(numberOfPoints + 1) * angleBetweenNormals, 4, 'Z')
        displacedVector = displacementVector.to_3d()
        displacedVector.rotate(rotationMatrix)
        resultingPoints.append(
            intersectionPoint + displacedVector * pointWidth)

    return resultingPoints


def createCirclePointsFromDiameter(rightPoint, leftPoint, numberOfPoints, counterClockwise=False):
    resultingPoints = []

    center = (rightPoint + leftPoint) / 2
    displacementVector = rightPoint - center

    angle = -1 * math.pi if not counterClockwise else math.pi

    resultingPoints.append(rightPoint)
    resultingPoints.extend(getPointsOnCurve(angle, numberOfPoints, displacementVector.length,
                                            displacementVector.length, displacementVector.normalized(), center))
    resultingPoints.append(leftPoint)

    return resultingPoints


# sliceHeight is the fraction between middle of the line and the top. Between -1 to 1
def offsetFunction(lineWidth, layerHeight, sliceHeight, roundness=0.5):
    halfLineWidth = lineWidth/2
    halfLayerHeight = layerHeight/2

    return halfLineWidth - halfLayerHeight * \
        (1 - math.sin(abs(1 - sliceHeight) * math.pi/2)) * roundness


# jointResolution is the angle after which to place a new point on a joint
def getOffsetCurvesForSegment(coords, sliceHeight=0, jointResolution=36 * math.pi / 180):
    rightOffsetPoints = []
    leftOffsetPoints = []

    zAxisVector = Vector((0, 0, 1))
    coordinateBuffer = []

    def zDeduction(h): return h - (sliceHeight + 1) * h / 2

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

            point1.z = point1.z - zDeduction(coord2["height"])
            point2.z = point2.z - zDeduction(coord2["height"])
            point3.z = point3.z - zDeduction(coord3["height"])

            firstOffset = offsetFunction(
                coord2["width"], coord2["height"], sliceHeight)
            secondOffset = offsetFunction(
                coord3["width"], coord3["height"], sliceHeight)

            firstVector = (point2 - point1).normalized()
            secondVector = (point3 - point2).normalized()

            firstNormal = firstVector.cross(zAxisVector).normalized()
            secondNormal = secondVector.cross(zAxisVector).normalized()

            angleBetween = (firstVector * -1).angle(secondVector)
            angleBetween = angleBetween if angleBetween < math.pi else math.pi * 2 - angleBetween

            intersectionVector = (firstVector * -1) * firstOffset/math.sin(
                angleBetween) + secondVector * secondOffset/math.sin(angleBetween)

            if i == 2:
                rightOffsetPoints.append([point1 + firstNormal*firstOffset])
                leftOffsetPoints.append([point1 - firstNormal*firstOffset])

            innerOffset = 'right' if firstVector.cross(
                secondVector).z < 0 else 'left'

            angleBetweenNormals = firstNormal.angle(secondNormal)
            angleBetweenNormals = angleBetweenNormals if angleBetweenNormals < math.pi else math.pi * \
                2 - angleBetweenNormals

            numberOfPoints = int(angleBetweenNormals // jointResolution)

            if innerOffset == 'right':
                rightOffsetPoints.append([point2 + intersectionVector])
                outerOffsetIntersections = []

                outerOffsetIntersections.append(
                    point2 - firstNormal * firstOffset)

                outerOffsetIntersections.extend(
                    getPointsOnCurve(-1 * angleBetweenNormals, numberOfPoints,
                                     firstOffset, secondOffset, -1 * firstNormal, point2)
                )

                outerOffsetIntersections.append(
                    point2 - secondNormal * secondOffset)

                leftOffsetPoints.append(outerOffsetIntersections)

            else:
                leftOffsetPoints.append([point2 + intersectionVector])

                outerOffsetIntersections = []

                outerOffsetIntersections.append(
                    point2 + firstNormal * firstOffset)

                outerOffsetIntersections.extend(
                    getPointsOnCurve(angleBetweenNormals, numberOfPoints,
                                     firstOffset, secondOffset,  firstNormal, point2)
                )

                outerOffsetIntersections.append(
                    point2 + secondNormal * secondOffset)

                rightOffsetPoints.append(outerOffsetIntersections)

            if i == len(coords) - 1:
                rightOffsetPoints.append(
                    [point3 + secondNormal * secondOffset])
                leftOffsetPoints.append([point3 - secondNormal * secondOffset])
                coordinateBuffer = []

        i += 1

    if len(coordinateBuffer) == 2:

        coord1, coord2 = (coordinateBuffer[0], coordinateBuffer[1])
        point1, point2 = (Vector(coord1["point"]), Vector(coord2["point"]))

        point1.z = point1.z - zDeduction(coord2["height"])
        point2.z = point2.z - zDeduction(coord2["height"])

        firstOffset = offsetFunction(
            coord2["width"], coord2["height"], sliceHeight)
        firstVector = (point2 - point1).normalized()

        firstNormal = firstVector.cross(zAxisVector).normalized()

        rightOffsetPoints.append([point1 + firstNormal*firstOffset])
        rightOffsetPoints.append([point2 + firstNormal*firstOffset])

        leftOffsetPoints.append([point1 - firstNormal*firstOffset])
        leftOffsetPoints.append([point2 - firstNormal*firstOffset])

    startCap = createCirclePointsFromDiameter(
        rightOffsetPoints[0][0], leftOffsetPoints[0][0], int(math.pi//jointResolution))

    endCap = createCirclePointsFromDiameter(
        rightOffsetPoints[-1][-1], leftOffsetPoints[-1][-1], int(math.pi//jointResolution), True)

    return {"right": rightOffsetPoints, "left": leftOffsetPoints, "start": startCap, "end": endCap}


def createTerminalSliceMesh(slice, bm, isTop=False):
    bottomSliceStartCapCenter = (
        slice["left"][0][0].co + slice["right"][0][0].co) / 2
    bottomSliceStartCapCenter = bm.verts.new(bottomSliceStartCapCenter)

    for i in range(len(slice["start"]) - 1):
        thisVertex = slice["start"][i]
        nextVertex = slice["start"][i + 1]

        face = bm.faces.new(
            [nextVertex, bottomSliceStartCapCenter, thisVertex])

        if isTop:
            face.normal_flip()

    for i in range(len(slice["left"]) - 1):
        leftStart = slice["left"][i][-1]
        rightStart = slice["right"][i][-1]

        leftEnd = slice["left"][i+1][0]
        rightEnd = slice["right"][i+1][0]

        face = bm.faces.new([rightStart, leftStart, leftEnd, rightEnd])
        if isTop:
            face.normal_flip()

        if len(slice["left"][i+1]) > 1:
            commonVertex = slice["right"][i+1][0]

            for j in range(len(slice["left"][i+1]) - 1):
                vert = slice["left"][i+1][j]
                nextVert = slice["left"][i+1][j + 1]

                face = bm.faces.new([nextVert, commonVertex, vert])
                if isTop:
                    face.normal_flip()

        if len(slice["right"][i+1]) > 1:
            commonVertex = slice["left"][i+1][0]

            for j in range(len(slice["right"][i+1]) - 1):
                vert = slice["right"][i+1][j]
                nextVert = slice["right"][i+1][j + 1]

                face = bm.faces.new([commonVertex, nextVert, vert])
                if isTop:
                    face.normal_flip()

    bottomSliceStartEndCenter = (
        slice["left"][-1][0].co + slice["right"][-1][0].co) / 2
    bottomSliceStartEndCenter = bm.verts.new(bottomSliceStartEndCenter)

    for i in range(len(slice["end"]) - 1):
        thisVertex = slice["end"][i]
        nextVertex = slice["end"][i + 1]

        face = bm.faces.new(
            [thisVertex, bottomSliceStartEndCenter, nextVertex])
        if isTop:
            face.normal_flip()


def placeSegmentAsMesh(segment, numberOfSlices, zPos, layerNumber, bm, params):
    if numberOfSlices % 2 == 0:
        raise Exception("number of slices must always be an odd number")

    halfSlice = int(numberOfSlices/2)
    slices = []

    for i in range(numberOfSlices):
        sliceFraction = (i - halfSlice)/halfSlice
        offsets = getOffsetCurvesForSegment(segment, sliceFraction)

        leftOffset = [[bm.verts.new((point.x, point.y, point.z))
                       for point in group] for group in offsets["left"]]
        rightOffset = [[bm.verts.new((point.x, point.y, point.z))
                        for point in group] for group in offsets["right"]]
        startCap = [bm.verts.new((point.x, point.y, point.z))
                    for point in offsets["start"]]
        endCap = [bm.verts.new((point.x, point.y, point.z))
                  for point in offsets["end"]]

        slices.append({"left": leftOffset, "right": rightOffset,
                      "start": startCap, "end": endCap})

    createTerminalSliceMesh(slices[0], bm)
    createTerminalSliceMesh(slices[-1], bm, True)

    for i in range(len(slices) - 1):
        slice = slices[i]
        nextSlice = slices[i + 1]

        sliceLeft = [point for group in slice["left"] for point in group]
        nextSliceLeft = [point for group in nextSlice["left"]
                         for point in group]

        for j in range(len(sliceLeft) - 1):
            bottomVertex1 = sliceLeft[j]
            bottomVertex2 = sliceLeft[j + 1]

            topVertex1 = nextSliceLeft[j]
            topVertex2 = nextSliceLeft[j + 1]

            bm.faces.new([bottomVertex1, topVertex1,
                          topVertex2, bottomVertex2])

        sliceRight = [point for group in slice["right"] for point in group]
        nextSliceRight = [point for group in nextSlice["right"]
                          for point in group]

        for j in range(len(sliceRight) - 1):
            bottomVertex1 = sliceRight[j]
            bottomVertex2 = sliceRight[j + 1]

            topVertex1 = nextSliceRight[j]
            topVertex2 = nextSliceRight[j + 1]

            bm.faces.new([bottomVertex1, bottomVertex2,
                          topVertex2, topVertex1])

        sliceStart = slice["start"]
        nextSliceStart = nextSlice["start"]

        for j in range(len(sliceStart) - 1):
            bottomVertex1 = sliceStart[j]
            bottomVertex2 = sliceStart[j + 1]

            topVertex1 = nextSliceStart[j]
            topVertex2 = nextSliceStart[j + 1]

            bm.faces.new([bottomVertex1, topVertex1,
                          topVertex2, bottomVertex2])

        sliceEnd = slice["end"]
        nextSliceEnd = nextSlice["end"]

        for j in range(len(sliceEnd) - 1):
            bottomVertex1 = sliceEnd[j]
            bottomVertex2 = sliceEnd[j + 1]

            topVertex1 = nextSliceEnd[j]
            topVertex2 = nextSliceEnd[j + 1]

            bm.faces.new([bottomVertex1, bottomVertex2,
                          topVertex2, topVertex1])


def placeSegmentAsCurve(segment, numberOfSlices, zPos, layerNumber, bm, params):
    if numberOfSlices % 2 == 0:
        raise Exception("number of slices must always be an odd number")

    halfSlice = int(numberOfSlices/2)
    slices = []

    for i in range(numberOfSlices):
        sliceFraction = (i - halfSlice)/halfSlice
        offsets = getOffsetCurvesForSegment(segment, sliceFraction)

        leftOffset = [(point.x, point.y, point.z)
                      for group in offsets["left"] for point in group]
        rightOffset = [(point.x, point.y, point.z)
                       for group in offsets["right"] for point in group]
        startCap = [(point.x, point.y, point.z)
                    for point in offsets["start"]]
        endCap = [(point.x, point.y, point.z)
                  for point in offsets["end"]]

        polyline = bm.splines.new('POLY')
        polyline.points.add(len(leftOffset) - 1)

        for idx, coord in enumerate(leftOffset):
            x, y, z = coord
            polyline.points[idx].co = (x, y, z, 1)

        polyline = bm.splines.new('POLY')
        polyline.points.add(len(startCap) - 1)

        for idx, coord in enumerate(startCap):
            x, y, z = coord
            polyline.points[idx].co = (x, y, z, 1)

        polyline = bm.splines.new('POLY')
        polyline.points.add(len(rightOffset) - 1)

        for idx, coord in enumerate(rightOffset):
            x, y, z = coord
            polyline.points[idx].co = (x, y, z, 1)

        polyline = bm.splines.new('POLY')
        polyline.points.add(len(endCap) - 1)

        for idx, coord in enumerate(endCap):
            x, y, z = coord
            polyline.points[idx].co = (x, y, z, 1)

    # polyline = mainCurveData.splines.new('POLY')
    # polyline.points.add(len(segment) - 1)

    # for idx, coord in enumerate(segment):
    #     x, y, z = coord["point"]
    #     polyline.points[idx].co = (x, y, z, 1)


def placeLayer(curves, zPos, layerNumber, collection, params):
    widthOffset = params[ParamNames.widthOffset]
    heightOffset = params[ParamNames.heightOffset]
    whPrecision = params[ParamNames.whPrecision]

    lengthOfCurve = 0

    # mainCurveData = bpy.data.curves.new('myCurve', type='CURVE')
    # mainCurveData.dimensions = '3D'
    # mainCurveData.resolution_u = 1
    # mainCurveData.render_resolution_u = 12

    meshData = bpy.data.meshes.new('myMesh')
    bm = bmesh.new()
    for curve in curves:
        coords = curve['coords']
        segments = getSegments(coords)

        visibilityPropertyIndex = bpy.context.scene.Stitcher_Props.TypesFiltersDict[
            curve['type']]
        isTypeVisible = bpy.context.scene.Stitcher_Props.TypesFiltersMap[
            visibilityPropertyIndex].value

        if (len(coords) > 1 and isTypeVisible):

            for segment in segments:
                placeSegmentAsMesh(segment, 7, 0,
                                   0, bm, params)
                # placeSegmentAsCurve(segment, 7, 0,
                #                     0, mainCurveData, params)

    bm.to_mesh(meshData)
    meshData.update()

    meshOB = bpy.data.objects.new(
        f'Layer_Main_{layerNumber}', meshData)

    # curveOB = bpy.data.objects.new(
    #     f'Layer_Main_{layerNumber}', mainCurveData)

    # Properties for debugging and other uses
    meshOB.data["zPos"] = zPos
    meshOB["zPos"] = zPos

    # curveOB.data["type"] = curveType
    # curveOB["type"] = curveType

    meshOB.data["lengthOfCurve"] = lengthOfCurve

    meshOB.data["layerNumber"] = layerNumber
    meshOB["layerNumber"] = layerNumber

    collection.objects.link(meshOB)
    # collection.objects.link(curveOB)

    return meshOB


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
