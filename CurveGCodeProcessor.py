
import math
from mathutils import Vector
import sys

moduleParentName = '.'.join(__name__.split('.')[:-1])
ImproperG2G3Exception = sys.modules[moduleParentName +
                                    '.Exceptions'].ImproperG2G3Exception


def g2g3IJFormCalculator(startingPosition, X, Y, Z, P, I, J, isG3, mm_per_segment=1):

    finalX = X if X != None else startingPosition['X']
    finalY = Y if Y != None else startingPosition['Y']
    finalZ = Z if Z != None else startingPosition['Z']

    zHeight = finalZ - startingPosition['Z']

    turns = P if P != None else 0

    centerX = startingPosition['X'] + I
    centerY = startingPosition['Y'] + J

    centerVector = Vector((centerX, centerY, 0))
    startVector = Vector(
        (startingPosition['X'] - centerX, startingPosition['Y'] - centerY, 0))
    endVector = Vector((finalX - centerX, finalY - centerY, 0))

    concernedVector = endVector if isG3 else startVector
    xAxis = Vector((1, 0, 0))

    angleBetweenConcernedVectorAndXAxis = concernedVector.angle(
        xAxis, 2*math.pi)
    crossVector = xAxis.cross(concernedVector)
    angleBetweenConcernedVectorAndXAxis = 2*math.pi - \
        angleBetweenConcernedVectorAndXAxis if crossVector.z < 0 else angleBetweenConcernedVectorAndXAxis

    angleCounterClockWise = startVector.angle(endVector, 0)

    crossVector = startVector.cross(endVector)

    angleCounterClockWise = 2*math.pi - \
        angleCounterClockWise if crossVector.z < 0 else angleCounterClockWise
    angleCounterClockWise = 2 * \
        math.pi if abs(angleCounterClockWise -
                       0) < 0.0001 else angleCounterClockWise

    angleClockWise = 2*math.pi - angleCounterClockWise
    angleClockWise = 2 * \
        math.pi if abs(angleClockWise - 0) < 0.0001 else angleClockWise

    if angleClockWise - 2*math.pi < 0.0001:
        turns -= 1

    angleCounterClockWise = angleCounterClockWise + 2*math.pi*turns
    angleClockWise = angleClockWise + 2*math.pi*turns

    radius = startVector.length

    concernedAngle = angleClockWise if isG3 else angleCounterClockWise
    concernedPitch = zHeight * (2*math.pi)/concernedAngle

    totalLengthOfMove = math.sqrt(
        (turns*2*math.pi*radius + concernedAngle*radius)**2 + zHeight**2)
    numberOfSteps = math.ceil(totalLengthOfMove/mm_per_segment)

    points = []
    for step in range(0, numberOfSteps+1):

        concernedStep = step if not isG3 else (numberOfSteps - step)
        currentAngle = concernedStep/numberOfSteps * \
            concernedAngle + angleBetweenConcernedVectorAndXAxis

        pitchAngle = step/numberOfSteps * concernedAngle

        pointX = radius*math.cos(currentAngle)
        pointY = radius*math.sin(currentAngle)
        pointZ = concernedPitch * pitchAngle/(2*math.pi)

        points.append(Vector((pointX, pointY, pointZ)))

    zOffsetVector = Vector((0, 0, startingPosition['Z']))
    return list(map(lambda x: x + centerVector + zOffsetVector, points))


def g2g3RFormCalculator(startingPosition, X, Y, Z, P, R, isG3, mm_per_segment=1):

    finalX = X if X else startingPosition['X']
    finalY = Y if Y else startingPosition['Y']

    if not X and not Y:
        raise ImproperG2G3Exception(
            "G2/G3 Commands in R form require at least one of X or Y")

    startPoint = Vector((startingPosition['X'], startingPosition['Y']))
    endPoint = Vector((finalX, finalY))

    midPoint = (startPoint + endPoint)/2
    distanceBetweenPoints = (startPoint - endPoint).length

    perpendicularUnitXClockwise = (
        endPoint.y - startPoint.y)/distanceBetweenPoints
    perpendicularUnitYClockwise = (
        startPoint.x - endPoint.x)/distanceBetweenPoints

    perpendicularUnitVectorClockwise = Vector(
        (perpendicularUnitXClockwise, perpendicularUnitYClockwise))

    centerDistanceFromMidpoint = math.sqrt(
        R**2 - ((distanceBetweenPoints)/2)**2)

    if distanceBetweenPoints > 2 * R:
        raise ImproperG2G3Exception(
            "Distance between points is greater than the diameter of the curve")

    if not isG3:
        center = midPoint + perpendicularUnitVectorClockwise * centerDistanceFromMidpoint

    else:
        center = midPoint - perpendicularUnitVectorClockwise * centerDistanceFromMidpoint

    IJ = center - startPoint

    return g2g3IJFormCalculator(startingPosition, finalX, finalY, Z, P,
                                IJ.x, IJ.y, isG3, mm_per_segment)


def isIJForm(commandDict):
    hasI = 'I' in commandDict and commandDict['I'] != None
    hasJ = 'J' in commandDict and commandDict['J'] != None
    hasR = 'R' in commandDict and commandDict['R'] != None

    if (hasI or hasJ) and not hasR:
        return True

    elif (hasI or hasJ) and hasR:
        ImproperG2G3Exception(
            "G2/G3 command should either contain I,J or R form. Not both at the same time")

    else:
        return False
