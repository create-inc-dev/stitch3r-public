import bpy, sys

from numpy import number


moduleParentName = '.'.join(__name__.split('.')[:-1])
Types = sys.modules[moduleParentName + '.Constants'].Types
objectProperties = sys.modules[moduleParentName + '.Constants'].objectProperties
Keywords = sys.modules[moduleParentName + '.Constants'].Keywords
GCodeReader = sys.modules[moduleParentName + '.GCodeReader']

def convertToMesh(curveOB):
    deg = bpy.context.evaluated_depsgraph_get()
    appliedMatrixWorld = curveOB.matrix_world.copy()
            
    meshData = bpy.data.meshes.new_from_object(curveOB.evaluated_get(deg))

    newObj = bpy.data.objects.new(curveOB.name+"_mesh", meshData)
    newObj.matrix_world = appliedMatrixWorld

    curveOB.users_collection[0].objects.link(newObj)

    for attr in curveOB.keys():
        if (attr in objectProperties):
            newObj[attr] = curveOB[attr]

    

    return newObj

def meshify(collection):
    allObjects = list(collection.all_objects)
    totalObjects = len(allObjects)
    processedObjects = 0
    numberOfEndPoints = 0

    for curveOB in allObjects:
        if (curveOB and curveOB.type == "CURVE" and curveOB["type"] == Types.endPoint):
            meshOB = convertToMesh(curveOB)
            parentOB = curveOB[Keywords.parent]

            if (curveOB == parentOB[Keywords.startPoint]):
                parentOB[Keywords.startPoint] = meshOB
            else:
                parentOB[Keywords.endPoint] = meshOB

            bpy.data.objects.remove(curveOB)
            
            processedObjects = processedObjects + 1
            numberOfEndPoints = numberOfEndPoints + 1
            print("Processed Objects: {}/{}".format(processedObjects, totalObjects), end="\r", flush=True)


            
    allObjects = list(collection.all_objects)
    for curveOB in allObjects:
        if (curveOB and curveOB.type == "CURVE" and curveOB["type"] != Types.endPoint):
            curveOB.data.resolution_u = curveOB.data.render_resolution_u

            curveDataName = curveOB.data.name
            meshOB = convertToMesh(curveOB) 

            if (Keywords.startPoint in meshOB.keys()):
                meshOB[Keywords.startPoint][Keywords.parent] = meshOB
                meshOB[Keywords.endPoint][Keywords.parent] = meshOB

            bpy.data.objects.remove(curveOB)
            bpy.data.curves.remove(bpy.data.curves.get(curveDataName))
            
            GCodeReader.addVisibilityDriver(meshOB, "hide_viewport")
            GCodeReader.addVisibilityDriver(meshOB, "hide_render")

            processedObjects = processedObjects + 1
            print("Processed Objects: {}/{}".format(processedObjects, totalObjects), end="\r", flush=True)

    print("")
    allObjects = list(collection.all_objects)

    processedObjects = 0
    for meshOB in allObjects:
        if (meshOB and meshOB.type == "MESH" and meshOB["type"] == Types.endPoint):
            GCodeReader.addVisibilityDriver(meshOB, "hide_viewport")
            GCodeReader.addVisibilityDriver(meshOB, "hide_render")

            processedObjects = processedObjects + 1
            print("Secondary Processing: {}/{}".format(processedObjects, numberOfEndPoints), end="\r", flush=True)

            

            




     

