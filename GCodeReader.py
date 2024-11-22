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
patternMatcherFunction = sys.modules[moduleParentName +
                                     '.Constants'].patternMatcherFunction
patternMatcherSearch = sys.modules[moduleParentName +
                                   '.Constants'].patternMatcherSearch
CurveGCodeProcessor = sys.modules[moduleParentName + '.CurveGCodeProcessor']


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

    # Pattern that matches G2 or G3 commands.
    curveGcodePattern = Patterns.curveGcodePattern
    # Matches the G0 or G1 commands that have no X,Y or Z components, thereby are not travel moves.
    nonMovingGcodePattern = Patterns.nonMovingGcodePattern
    # Detecting Layer change, I think this makes things incompatible with vase mode.
    layerChangePattern = Patterns.printerSpecificPatterns[
        params[ParamNames.slicer]]['layerChangePattern']
    # Detecting a change in the width of print line
    widthPattern = Patterns.printerSpecificPatterns[params[ParamNames.slicer]]['widthPattern']
    zPosPattern = Patterns.printerSpecificPatterns[params[ParamNames.slicer]]['zPosPattern']
    heightPattern = Patterns.printerSpecificPatterns[params[ParamNames.slicer]]['heightPattern']
    typePattern = Patterns.printerSpecificPatterns[params[ParamNames.slicer]]['typePattern']
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

    while True:
        try:
            line = next(linesIterator)
        except StopIteration:
            line = "!__end__!"

        curLineNumber = curLineNumber + 1

        if patternMatcherFunction(gcodePattern, line):

            gcodePart = patternMatcherSearch(gcodePattern, line)[1].strip()
            """commentPart = "" ##Only needed if there is a need to process comments later

            try:
                commentPart = gcodePattern.search(line)[2].strip()
            except (IndexError, AttributeError):
                pass"""

            separatedGcode = gcodePart.split()
            tempDict = valueTacker.copy()

            # Ignore any GCode G0/G1 command that doesn't move the extruder
            if not patternMatcherFunction(nonMovingGcodePattern, gcodePart):

                for term in separatedGcode:
                    tempDict[term[0]] = float(term[1:])
                    if term[0] in ['X', 'Y', 'Z']:
                        valueTacker[term[0]] = float(term[1:])
                tempDict['lineNumber'] = curLineNumber

                prevLayerGcodes.append(tempDict.copy())

        if patternMatcherFunction(curveGcodePattern, line):
            matchObject = patternMatcherSearch(curveGcodePattern, line)
            gcodePart = matchObject[1].strip()
            commandNumber = matchObject[2]

            isG2 = commandNumber == '2'

            separatedGcode = gcodePart.split()
            tempDict = valueTacker.copy()

            curveCommandDict = {}

            for term in separatedGcode:
                termCode = term[0]
                termNumber = float(term[1:])

                curveCommandDict[termCode] = termNumber

            for termCode in ['X', 'Y', 'Z', 'P', 'I', 'J', 'R', 'E']:
                if not termCode in curveCommandDict:
                    curveCommandDict[termCode] = None

            isIJCommand = CurveGCodeProcessor.isIJForm(curveCommandDict)

            if isIJCommand:
                points = CurveGCodeProcessor.g2g3IJFormCalculator(valueTacker, curveCommandDict['X'], curveCommandDict['Y'], curveCommandDict['Z'],
                                                                  curveCommandDict['P'], curveCommandDict['I'], curveCommandDict['J'], isG2, valueTacker['W']*3)
            else:
                points = CurveGCodeProcessor.g2g3RFormCalculator(valueTacker, curveCommandDict['X'], curveCommandDict['Y'], curveCommandDict['Z'],
                                                                 curveCommandDict['P'], curveCommandDict['R'], isG2, valueTacker['W']*3)

            for term in ['X', 'Y', 'Z']:
                if curveCommandDict[term] != None:
                    valueTacker[term] = curveCommandDict[term]

            for point in points:
                tempDict['X'] = point.x
                tempDict['Y'] = point.y
                tempDict['Z'] = point.z
                tempDict['E'] = 1 if curveCommandDict['E'] else 0

                tempDict['lineNumber'] = curLineNumber
                prevLayerGcodes.append(tempDict.copy())

        # In case of layer change, push the accumulated GCodes of previous layer and start accumulating the next one.
        elif patternMatcherFunction(layerChangePattern, line):
            zPos = 0
            height = 0

            try:
                line = next(linesIterator)
                curLineNumber = curLineNumber + 1
                zPos = float(patternMatcherSearch(zPosPattern, line)[1])
            except (IndexError, TypeError):
                raise NoZPosMatch(line, curLineNumber)

            try:
                line = next(linesIterator)
                curLineNumber = curLineNumber + 1
                height = float(patternMatcherSearch(heightPattern, line)[1])
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

        elif patternMatcherFunction(heightPattern, line):
            valueTacker['H'] = float(
                patternMatcherSearch(heightPattern, line)[1])

        elif patternMatcherFunction(widthPattern, line):
            valueTacker['W'] = float(
                patternMatcherSearch(widthPattern, line)[1])

        elif patternMatcherFunction(typePattern, line):
            curveType = patternMatcherSearch(typePattern, line)[1].strip()
            valueTacker['type'] = re.sub(" |/", "_", curveType)

        elif patternMatcherFunction(filamentChangePattern, line):
            filamentNumber = int(patternMatcherSearch(
                filamentChangePattern, line)[1].strip())
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


def addTransformationConstraint(meshOB, parent):
    constraint = meshOB.constraints.new(type='COPY_TRANSFORMS')
    constraint.target = parent


def addLayerHeightProperty(layerHeight, layerNumber,  parent):
    try:
        heights = parent["layer_heights"]
    except KeyError:
        heights = None
    if heights:
        heights = list(heights)
        heights[layerNumber] = layerHeight
        parent[Keywords.layerHeight] = heights
    else:
        parent[Keywords.layerHeight] = [layerHeight]


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

                if (newStartingPoint - point).length > 0.00001:
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

                if (newEndingPoint - point).length > 0.00001:
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


def simplifyPolyline(coords, mergeAngle, startI):
    newCoords = []

    i = startI
    i += 1

    newCoords.extend(coords[:i])
    merged = False

    while (i < len(coords) - 1):
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
        else:
            merged = True

        newCoords.append(coord3)
        i += 2

    if i == len(coords) - 1:
        newCoords.append(coords[-1])

    return [merged, newCoords]


def getSegments(coords, coin, params):

    mergeAngle = (180 - params[ParamNames.mergeAngle]) * math.pi/180

    newCoords = coords
    timesNotMerged = 0
    i = 0
    while timesNotMerged < 2:
        merged, newCoords = simplifyPolyline(newCoords, mergeAngle, i)
        i = (i+1) % 2

        if merged:
            timesNotMerged = 0
        else:
            timesNotMerged += 1

    segments = []
    currentSegment = []

    newCoords = removeSeamDistance(newCoords, coin, params)

    if (len(newCoords) == 2):
        return [newCoords]

    coordinateBuffer = []
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

            angleBetweenVectors = firstVector.angle(secondVector)

            if angleBetweenVectors != 0 and firstVector.length < secondOffset / abs(math.sin(angleBetweenVectors)):
                if len(currentSegment) > 0:
                    segments.append(currentSegment)
                    currentSegment = []

                segments.append([coord1, coord2])

                if i == len(newCoords) - 1:
                    segments.append([coord2, coord3])

            elif angleBetweenVectors != 0 and secondVector.length < firstOffset / abs(math.sin(angleBetweenVectors)):
                if len(currentSegment) == 0:
                    currentSegment.append(coord1)

                currentSegment.append(coord2)
                segments.append(currentSegment)
                currentSegment = []

                if i == len(newCoords) - 1:
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


def placeSegmentAsMesh(segment, numberOfSlices,  filamentNumber,  bm, segNo, params):
    steps = 20
    segNo = segNo % (steps + 1)

    negativeOffset = -1 * params[ParamNames.zFightingStagger]
    positiveOffset = params[ParamNames.zFightingStagger]

    randomHeightOffset = negativeOffset + \
        (positiveOffset - negativeOffset)/steps * \
        segNo + Random().uniform(-0.001, 0.001)

    halfSlice = int(numberOfSlices/2)
    slices = []

    jointResolution = params[ParamNames.degreesPerJointPoint] * math.pi / 180

    for i in range(numberOfSlices):
        sliceFraction = (i - halfSlice)/halfSlice
        offsets = getOffsetCurvesForSegment(
            segment, sliceFraction, jointResolution)

        leftOffset = [[bm.verts.new((point.x, point.y, point.z + randomHeightOffset))
                       for point in group] for group in offsets["left"]]
        rightOffset = [[bm.verts.new((point.x, point.y, point.z + randomHeightOffset))
                        for point in group] for group in offsets["right"]]
        startCap = [bm.verts.new((point.x, point.y, point.z + randomHeightOffset))
                    for point in offsets["start"]]
        endCap = [bm.verts.new((point.x, point.y, point.z + randomHeightOffset))
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


def isVerySmallSegment(segment):
    if len(segment) == 2:
        point1 = Vector(segment[0]["point"])
        point2 = Vector(segment[1]["point"])
        if (point2 - point1).length < 0.001:
            return True

    elif len(segment) < 2:
        return True

    else:
        return False


def placeLayer(curves, zPos, layerNumber, collection, coin, params):

    lengthOfCurve = 0
    materials = bpy.context.scene.Stitcher_Props.materials

    meshData = bpy.data.meshes.new('myMesh')
    bm = bmesh.new()
    numberOfSlices = params[ParamNames.SlicesPerPrintLine]

    for curve in curves:
        coords = curve['coords']
        filamentNumber = curve['filament']

        if (len(coords) > 1):
            segments = getSegments(coords, coin, params)
            segNo = 0
            for segment in segments:

                if not isVerySmallSegment(segment):
                    placeSegmentAsMesh(segment, numberOfSlices,
                                       filamentNumber, bm, segNo, params)
                    segNo += 1

    bm.to_mesh(meshData)
    meshData.update()

    meshOB = bpy.data.objects.new(
        f'Layer_Main_{layerNumber}', meshData)

    for material in materials:
        mat = bpy.data.materials.get(material)
        meshOB.data.materials.append(mat)

    meshOB.data["zPos"] = zPos
    meshOB["zPos"] = zPos

    meshOB["type"] = Keywords.meshObject

    meshOB.data["lengthOfCurve"] = lengthOfCurve

    meshOB.data["layerNumber"] = layerNumber
    meshOB["layerNumber"] = layerNumber

    collection.objects.link(meshOB)

    addVisibilityDriver(meshOB)
    addVisibilityDriver(meshOB, "hide_render")

    addTransformationConstraint(meshOB, params[ParamNames.parent])
    addLayerHeightProperty(zPos, layerNumber, params[ParamNames.parent])

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
