from ast import Param
from random import Random
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
getFilamentName = sys.modules[moduleParentName + '.Constants'].getFilamentName
Patterns = sys.modules[moduleParentName + '.Constants'].Patterns


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
    gcodePattern = Patterns.gcodePattern
    # Matches the G0 or G1 commands that have no X,Y or Z components, thereby are not travel moves.
    nonMovingGcodePattern = Patterns.nonMovingGcodePattern
    # Detecting Layer change, I think this makes things incompatible with vase mode.
    layerChangePattern = Patterns.printerSpecificPatterns['orca']['layerChangePattern']
    # Detecting a change in the width of print line
    widthPattern = Patterns.printerSpecificPatterns['orca']['widthPattern']
    zPosPattern = Patterns.printerSpecificPatterns['orca']['zPosPattern']
    heightPattern = Patterns.printerSpecificPatterns['orca']['heightPattern']
    typePattern = Patterns.printerSpecificPatterns['orca']['typePattern']
    filamentChangePattern = Patterns.filamentChangePattern

    prevLayerGcodes = []  # All GCodes that move the nozzle, with our without extrusion would be stored here and then popped when the next later starts
    # Prusa Slicer Prints the Z position and layer height after each layer change
    prevLayerZPos = 0
    prevLayerHeight = 0
    curLineNumber = 0  # For error tracing
    curLayerNumber = 0

    # E is extrusion; X, Y and Z are the coordinates; W is width of the  print line
    valueTacker = {'X': 0, 'Y': 0, 'Z': 0, 'E': 0, 'W': 0.5,
                   'H': 0.2, 'layerNumber': 0, 'type': 'Custom', 'filament': 0}

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
                height = float(heightPattern.search(line)[1])
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
            valueTacker['H'] = float(heightPattern.search(line)[1])

        elif bool(widthPattern.match(line)):
            valueTacker['W'] = float(widthPattern.search(line)[1])

        elif bool(typePattern.match(line)):
            curveType = typePattern.search(line)[1].strip()
            valueTacker['type'] = re.sub(" |/", "_", curveType)

        elif bool(filamentChangePattern.match(line)):
            filamentNumber = int(filamentChangePattern.search(line)[1].strip())
            valueTacker['filament'] = filamentNumber

        elif line == "!__end__!":
            prevLayer = Layer(prevLayerZPos, prevLayerHeight,
                              curLayerNumber, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)
            break

        else:
            pass

    return listOfParsedLayers


def addVisibilityDriver(curveOB, drivenProperty="hide_viewport"):

    driver = curveOB.driver_add(drivenProperty).driver
    var0 = driver.variables.new()
    var0.name = "var0"
    var0.targets[0].id_type = 'SCENE'
    var0.targets[0].id = bpy.context.scene
    var0.targets[0].data_path = "Stitcher_Props.LayerIndexTop"

    var1 = driver.variables.new()
    var1.name = "var2"
    var1.targets[0].id = curveOB
    var1.targets[0].data_path = '["layerNumber"]'

    condition2 = "({0} <= {1})".format(var1.name, var0.name)

    driver.expression = "not ({0})".format(condition2)


# Apply modifier to smooth out overlap artefacts, only shows in renders
def addEnhancingModifiers(curveOB):
    curveOB.modifiers.new('split', 'EDGE_SPLIT')
    curveOB.modifiers.get('split').show_viewport = False


def removeSeamDistance(coords, coin, params):
    seamDistance = params[ParamNames.seamDistance]

    headProb = params[ParamNames.seamAbberations][ParamNames.probability]
    abbAmount = params[ParamNames.seamAbberations][ParamNames.amount]

    if (coin.toss(headProb)):
        startingSeam = (seamDistance + coin.uniform(0, abbAmount))/2
    else:
        startingSeam = seamDistance/2

    if (coin.toss(headProb)):
        endingSeam = (seamDistance + coin.uniform(0, abbAmount))/2
    else:
        endingSeam = seamDistance/2

    try:
        lengthSoFar = 0
        prevCoord = coords.pop(0)

        while len(coords) > 0:
            coord = coords[0]

            point = Vector(coord["point"])
            prevPoint = Vector(prevCoord["point"])

            if (point - prevPoint).length + lengthSoFar > startingSeam:
                unitVector = (point - prevPoint).normalized()
                newStartingPoint = prevPoint + startingSeam * unitVector
                newCoord = {'point': newStartingPoint,
                            'width': coord['width'],
                            'height': coord['height']}

                coords.insert(0, newCoord)
                break
            else:
                prevCoord = coords.pop(0)
                lengthSoFar += (point - prevPoint).length

        lengthSoFar = 0
        prevCoord = coords.pop()

        while len(coords) > 0:
            coord = coords[-1]

            point = Vector(coord["point"])
            prevPoint = Vector(prevCoord["point"])

            if (point - prevPoint).length + lengthSoFar > endingSeam:
                unitVector = (point - prevPoint).normalized()
                newEndingPoint = prevPoint + endingSeam * unitVector
                newCoord = {'point': newEndingPoint,
                            'width': coord['width'],
                            'height': coord['height']}

                coords.append(newCoord)
                break
            else:
                prevCoord = coords.pop()
                lengthSoFar += (point - prevPoint).length
    except IndexError:
        coords = []

    return coords


def getSegments(coords, coin, params):

    mergeAngle = (180 - params[ParamNames.mergeAngle]) * math.pi/180

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

    newCoords = removeSeamDistance(newCoords, coin, params)
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
def getOffsetCurvesForSegment(coords, sliceHeight=0, jointResolution=9 * math.pi / 180):
    randomHeightOffset = 0  # Random().uniform(0, 0.001)

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

            point1.z = point1.z - \
                zDeduction(coord2["height"] + randomHeightOffset)
            point2.z = point2.z - \
                zDeduction(coord2["height"] + randomHeightOffset)
            point3.z = point3.z - \
                zDeduction(coord3["height"] + randomHeightOffset)

            firstOffset = offsetFunction(
                coord2["width"] + randomHeightOffset, coord2["height"] + randomHeightOffset, sliceHeight)
            secondOffset = offsetFunction(
                coord3["width"] + randomHeightOffset, coord3["height"] + randomHeightOffset, sliceHeight)

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

        point1.z = point1.z - zDeduction(coord2["height"] + randomHeightOffset)
        point2.z = point2.z - zDeduction(coord2["height"] + randomHeightOffset)

        firstOffset = offsetFunction(
            coord2["width"] + randomHeightOffset, coord2["height"] + randomHeightOffset, sliceHeight)
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


def createTerminalSliceMesh(slice, bm, filamentNumber, isTop=False):
    bottomSliceStartCapCenter = (
        slice["left"][0][0].co + slice["right"][0][0].co) / 2
    bottomSliceStartCapCenter = bm.verts.new(bottomSliceStartCapCenter)

    for i in range(len(slice["start"]) - 1):
        thisVertex = slice["start"][i]
        nextVertex = slice["start"][i + 1]

        face = bm.faces.new(
            [nextVertex, bottomSliceStartCapCenter, thisVertex])

        face.material_index = filamentNumber

        if isTop:
            face.normal_flip()

    for i in range(len(slice["left"]) - 1):
        leftStart = slice["left"][i][-1]
        rightStart = slice["right"][i][-1]

        leftEnd = slice["left"][i+1][0]
        rightEnd = slice["right"][i+1][0]

        face = bm.faces.new([rightStart, leftStart, leftEnd, rightEnd])
        face.material_index = filamentNumber
        if isTop:
            face.normal_flip()

        if len(slice["left"][i+1]) > 1:
            commonVertex = slice["right"][i+1][0]

            for j in range(len(slice["left"][i+1]) - 1):
                vert = slice["left"][i+1][j]
                nextVert = slice["left"][i+1][j + 1]

                face = bm.faces.new([nextVert, commonVertex, vert])
                face.material_index = filamentNumber
                if isTop:
                    face.normal_flip()

        if len(slice["right"][i+1]) > 1:
            commonVertex = slice["left"][i+1][0]

            for j in range(len(slice["right"][i+1]) - 1):
                vert = slice["right"][i+1][j]
                nextVert = slice["right"][i+1][j + 1]

                face = bm.faces.new([commonVertex, nextVert, vert])
                face.material_index = filamentNumber
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
        face.material_index = filamentNumber
        if isTop:
            face.normal_flip()


def placeSegmentAsMesh(segment, numberOfSlices,  filamentNumber,  bm, params):
    if numberOfSlices % 2 == 0:
        raise Exception("number of slices must always be an odd number")

    halfSlice = int(numberOfSlices/2)
    slices = []

    jointResolution = params[ParamNames.degreesPerJointPoint] * math.pi / 180

    for i in range(numberOfSlices):
        sliceFraction = (i - halfSlice)/halfSlice
        offsets = getOffsetCurvesForSegment(
            segment, sliceFraction, jointResolution)

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

    createTerminalSliceMesh(slices[0], bm, filamentNumber)
    createTerminalSliceMesh(slices[-1], bm, filamentNumber, True)

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

            face = bm.faces.new([bottomVertex1, topVertex1,
                                 topVertex2, bottomVertex2])
            face.material_index = filamentNumber

        sliceRight = [point for group in slice["right"] for point in group]
        nextSliceRight = [point for group in nextSlice["right"]
                          for point in group]

        for j in range(len(sliceRight) - 1):
            bottomVertex1 = sliceRight[j]
            bottomVertex2 = sliceRight[j + 1]

            topVertex1 = nextSliceRight[j]
            topVertex2 = nextSliceRight[j + 1]

            face = bm.faces.new([bottomVertex1, bottomVertex2,
                                 topVertex2, topVertex1])
            face.material_index = filamentNumber

        sliceStart = slice["start"]
        nextSliceStart = nextSlice["start"]

        for j in range(len(sliceStart) - 1):
            bottomVertex1 = sliceStart[j]
            bottomVertex2 = sliceStart[j + 1]

            topVertex1 = nextSliceStart[j]
            topVertex2 = nextSliceStart[j + 1]

            face = bm.faces.new([bottomVertex1, topVertex1,
                                 topVertex2, bottomVertex2])
            face.material_index = filamentNumber

        sliceEnd = slice["end"]
        nextSliceEnd = nextSlice["end"]

        for j in range(len(sliceEnd) - 1):
            bottomVertex1 = sliceEnd[j]
            bottomVertex2 = sliceEnd[j + 1]

            topVertex1 = nextSliceEnd[j]
            topVertex2 = nextSliceEnd[j + 1]

            face = bm.faces.new([bottomVertex1, bottomVertex2,
                                 topVertex2, topVertex1])
            face.material_index = filamentNumber


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


def placeLayer(curves, zPos, layerNumber, collection, coin, params):
    widthOffset = params[ParamNames.widthOffset]
    heightOffset = params[ParamNames.heightOffset]

    lengthOfCurve = 0
    materials = bpy.context.scene.Stitcher_Props.materials

    # mainCurveData = bpy.data.curves.new('myCurve', type='CURVE')
    # mainCurveData.dimensions = '3D'
    # mainCurveData.resolution_u = 1
    # mainCurveData.render_resolution_u = 12

    meshData = bpy.data.meshes.new('myMesh')
    bm = bmesh.new()
    for curve in curves:
        coords = curve['coords']
        filamentNumber = curve['filament']

        visibilityPropertyIndex = bpy.context.scene.Stitcher_Props.TypesFiltersDict[
            curve['type']]
        isTypeVisible = bpy.context.scene.Stitcher_Props.TypesFiltersMap[
            visibilityPropertyIndex].value

        if (len(coords) > 1 and isTypeVisible):
            segments = getSegments(coords, coin, params)
            for segment in segments:
                placeSegmentAsMesh(segment, 7, filamentNumber, bm, params)
                # placeSegmentAsCurve(segment, 7, 0,
                #                     0, mainCurveData, params)

    bm.to_mesh(meshData)
    meshData.update()

    meshOB = bpy.data.objects.new(
        f'Layer_Main_{layerNumber}', meshData)

    for material in materials:
        mat = bpy.data.materials.get(material)
        meshOB.data.materials.append(mat)

    # curveOB = bpy.data.objects.new(
    #     f'Layer_Main_{layerNumber}', mainCurveData)

    # Properties for debugging and other uses
    meshOB.data["zPos"] = zPos
    meshOB["zPos"] = zPos

    # curveOB.data["type"] = curveType
    meshOB["type"] = Keywords.meshObject

    meshOB.data["lengthOfCurve"] = lengthOfCurve

    meshOB.data["layerNumber"] = layerNumber
    meshOB["layerNumber"] = layerNumber

    collection.objects.link(meshOB)

    addVisibilityDriver(meshOB)
    addVisibilityDriver(meshOB, "hide_render")
    # collection.objects.link(curveOB)

    return meshOB


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
