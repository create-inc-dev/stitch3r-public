import bpy, sys

from numpy import number


moduleParentName = '.'.join(__name__.split('.')[:-1])
Types = sys.modules[moduleParentName + '.Constants'].Types
objectProperties = sys.modules[moduleParentName + '.Constants'].objectProperties
Keywords = sys.modules[moduleParentName + '.Constants'].Keywords
GCodeReader = sys.modules[moduleParentName + '.GCodeReader']
ExtruderErrorCreator = sys.modules[moduleParentName + '.ExtruderErrorCreator']

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
    

    for obj in bpy.context.selected_objects:
        obj.select_set(False)

    for curveOB in allObjects:
        if (curveOB and curveOB.type == "CURVE" and curveOB["type"] == Types.endPoint):
            appliedMatrixWorld = curveOB.matrix_world.copy()
            
            for d in curveOB.animation_data.drivers:
                if (d.data_path == 'constraints["Follow Path"].offset_factor'):
                    curveOB.animation_data.drivers.remove(d)

            for c in curveOB.constraints:
                curveOB.constraints.remove(c)

            curveOB.matrix_world = appliedMatrixWorld

        if (curveOB and curveOB.type == "CURVE" and curveOB["type"] != Types.endPoint):
            curveOB.modifiers.get('split').show_viewport = True
            curveOB.data.resolution_u = curveOB.data.render_resolution_u
        
        processedObjects  = processedObjects + 1
        print("Prepropcessing for meshify done: {}/{}".format(processedObjects, totalObjects), end='\r', flush=True)
        curveOB.select_set(True)


    print("\nRunning Convert To Mesh Operation")
    bpy.context.view_layer.objects.active = allObjects[0]
    bpy.ops.object.convert(target="MESH")


            




     

