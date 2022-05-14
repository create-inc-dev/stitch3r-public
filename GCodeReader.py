import bpy
import bmesh
from mathutils import Vector
from bpy import context 
import re 

class Layer: #Class that stores information about the layer. Needs to change because there are different widths in the same layer as well
    def __init__(self, zPos, height, gcodes) -> None:
        self.zPos = zPos
        self.height = height
        self.gcodes = gcodes


#Reads the GCode Files, extracts only the G1 and G0 moves. Sorry no support for circular moves so far.
def gcodeParser(gcodeFilePath):
    file = open(gcodeFilePath, 'r')
    
    listOfParsedLayers = []
    
    gcodePattern = re.compile("\s*G[01](\s+[XYZEF](-?[0-9]+(\.[0-9]+)?))+\s*$") #Pattern that matches G0 or G1 commands. To be noted, I don't see any G0 commansd in Prusa Slicer.
    nonMovingGcodePattern = re.compile("\s*G[01](\s+[EF](-?[0-9]+(\.[0-9]+)?))+\s*$") #Matches the G0 or G1 commands that have no X,Y or Z components, thereby are not travel moves.
    layerChangePattern = re.compile("\s*;LAYER_CHANGE\s*") #Detecting Layer change, I think this makes things incompatible with vase mode.
    prevLayerGcodes = []
    prevLayerZPos = 0
    prevLayerHeight = 0

    curPosValues = {'X':0, 'Y':0, 'Z':0, 'E':0, 'W':0.5}
    while True:
        line = file.readline()
        

        if bool(layerChangePattern.match(line)):
            zPos = float(file.readline().split(":")[-1])
            height = float(file.readline().split(":")[-1])

            prevLayer = Layer(prevLayerZPos, prevLayerHeight, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)

            
            prevLayerGcodes = []
            prevLayerZPos = zPos
            prevLayerHeight = height

            


        elif bool(gcodePattern.match(line)):
            separatedGcode = line.split()
            tempDict = curPosValues.copy()
            
            if not bool(nonMovingGcodePattern.match(line)):
                for term in separatedGcode:
                    tempDict[term[0]] = float(term[1:])
                    if term[0] in ['X', 'Y', 'Z']:
                        curPosValues[term[0]] = float(term[1:])
                
                prevLayerGcodes.append(tempDict.copy())
            
            
        

        elif not line:
            prevLayer = Layer(prevLayerZPos, prevLayerHeight, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)
            break

    return listOfParsedLayers

def builder(gcodeFilePath):
    
    listOfParsedLayers = gcodeParser(gcodeFilePath)

    
    i = 0
    for currentLayer in listOfParsedLayers:
        
        coords = []

        for elem in currentLayer.gcodes:
            print(elem) 
            if (elem["E"] > 0):
                
                coords.append((elem["X"],elem["Y"],elem["Z"]))

       
        curveData = bpy.data.curves.new('myCurve' + str(i) , type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 1

        polyline = curveData.splines.new('POLY')
        polyline.points.add(len(coords)-1)
        for i, coord in enumerate(coords):
            x,y,z = coord
            polyline.points[i].co = (x, y, z, 1)

        view_layer = bpy.context.view_layer
        curveOB = bpy.data.objects.new('myCurve' + str(i), curveData)
        curveData.bevel_mode = "OBJECT"
        curveData.bevel_object = bpy.data.objects.get("bevelObject")
        view_layer.active_layer_collection.collection.objects.link(curveOB)

        i = i + 1

            
if __name__ == "__main__": builder("/Users/vipulrajan/Downloads/benchy.gcode")

"""def slicer(ob, start, end, cuts):
    #slices = [] could instead return unlinked objects
    axis = end - start
    dv = axis / cuts
    #axis.normalize()
    mw = ob.matrix_world
    bm0 = bm = bmesh.new()
    
    # transform to world coords
    # bm.transform(mw)
    # mesh = bpy.data.meshes.new("Slice")

    for i in range(cuts + 1):
        bm.from_mesh(ob.data)
        #bm.from_object(ob, dg) # use modified mesh
        #bm = bm0.copy()
        #bm.transform(mw) # make global
        plane_co = start + i * dv
       
        cut = bmesh.ops.bisect_plane(
                bm,
                plane_co=plane_co,
                plane_no=axis,
                geom=bm.verts[:] + bm.faces[:] + bm.edges[:],
                clear_inner=True,
                clear_outer=True,
                )["geom_cut"]
        if not cut:
            bm.clear()
            continue
        me = bpy.data.meshes.new(f"Slice{i}")
        # me = mesh.copy()
        bm.to_mesh(me)
        '''
        # only slightly slower
        me.from_pydata(
            [v.co for v in cut if hasattr(v, "co")],
            [(e.verts[0].index, e.verts[1].index) for e in cut if hasattr(e, "verts")],
            []
            )
        '''

        slice = bpy.data.objects.new(f"Slice{i}", me)
        slice.matrix_world = mw
        context.collection.objects.link(slice)
        bm.clear()        
        #bm.free() # if using bm = bm0.copy()
    #bm.free()
    
slicer(
        context.object, 
        Vector((0, 0, -1)), 
        Vector((0, 0, 1)), 
        100)"""