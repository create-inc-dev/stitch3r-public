import math
from mathutils import Vector, Matrix


def g2g3IJFormCalculator(startingPosition, X, Y, I, J, isG2, mm_per_segment=1):

    finalX = X if X else startingPosition['X']
    finalY = Y if Y else startingPosition['Y']

    centerX = startingPosition['X'] + I
    centerY = startingPosition['Y'] + J

    centerVector = Vector((centerX, centerY, 0))
    startVector = Vector(
        (startingPosition['X'] - centerX, startingPosition['Y'] - centerY, 0))
    endVector = Vector((finalX - centerX, finalY - centerY, 0))

    angleCounterClockWise = startVector.angle(endVector, math.pi)

    crossVector = startVector.cross(endVector)

    angleCounterClockWise = 2*math.pi - \
        angleCounterClockWise if crossVector.z < 0 else angleCounterClockWise

    angleClockWise = 2*math.pi - angleCounterClockWise

    radius = startVector.length

    angleStep = 2*math.asin(mm_per_segment/(2 * radius))
    currentAngle = 0
    points = []

    concernedAngle = angleClockWise if isG2 else angleCounterClockWise

    while currentAngle < concernedAngle:

        rotationMatrix = Matrix.Rotation(
            -1 * currentAngle, 4, 'Z') if isG2 else Matrix.Rotation(
            currentAngle, 4, 'Z')

        startVectorDup = startVector.to_3d()
        startVectorDup.rotate(rotationMatrix)
        points.append(startVectorDup)
        currentAngle += angleStep

    finalPointRotationMatrix = Matrix.Rotation(
        -1 * concernedAngle, 4, 'Z') if isG2 else Matrix.Rotation(
        concernedAngle, 4, 'Z')

    startVectorDup = startVector.to_3d()
    startVectorDup.rotate(finalPointRotationMatrix)

    finalPoint = startVectorDup

    if (finalPoint - points[-1]).length > 0.0001:
        points.append(finalPoint)

    return list(map(lambda x: x + centerVector, points))


def g2g3RFormCalculator(startingPosition, X, Y, R, isG2, mm_per_segment=1):

    finalX = X if X else startingPosition['X']
    finalY = Y if Y else startingPosition['Y']

    if not X and not Y:
        raise Exception("something went wrong")

    startPoint = Vector((startingPosition['X'], startingPosition['Y']))
    endPoint = Vector((finalX, finalY))
    
    midPoint = (startPoint + endPoint)/2
    distanceBetweenPoints = (startPoint - endPoint).length
    
    perpendicularUnitX = -(endPoint.y - startPoint.y)/distanceBetweenPoints
    perpendicularUnitY = endPoint.x - startPoint.x/distanceBetweenPoints
    
    perpendicularUnitVector = Vector((perpendicularUnitX, perpendicularUnitY))
    

    
    
    
    
    if distanceBetweenPoints > 2 *R:
        raise Exception("something went wrong")
    
    
    
# points = g2g3IJFormCalculator(
#     {'X': 0, 'Y': 0, 'Z': 0}, 10, 10, 0, 10, True, 1)

points = g2g3IJFormCalculator(
    {'X': 0, 'Y': 0, 'Z': 0}, 10, 10, 10, True, 1)

# print(len(points))
# print(points)
for point in points:
    print("({x},{y}),".format(x=point.x, y=point.y), end="")

print()
