from http.client import LineTooLong
from importlib import import_module
import bpy
import os, sys
import bmesh
from mathutils import Vector
from bpy import context 
import re 
import importlib

moduleParentName = '.'.join(__name__.split('.')[:-1])
createProfile = sys.modules[moduleParentName + '.BevelShapeCreator'].createProfile
NoZPosMatch = sys.modules[moduleParentName + '.Exceptions'].NoZPosMatch
NoHeightMatch = sys.modules[moduleParentName + '.Exceptions'].NoHeightMatch
NoSuchPropertyException = sys.modules[moduleParentName + '.Exceptions'].NoSuchPropertyException

class Layer: #Class that stores information about the layer. Needs to change because there are different widths in the same layer as well
    def __init__(self, zPos, height, layerNumber, gcodes) -> None:
        self.zPos = zPos
        self.layerNumber = layerNumber
        self.height = height
        self.gcodes = gcodes
    def __str__(self) -> str:
        return "zPos:{0} | height:{1} | {2}".format(self.zPos, self.height, self.gcodes)


#Reads the GCode Files, extracts only the G1 and G0 moves. Sorry no support for circular moves so far.
def gcodeParser(gcodeFilePath, params):
    file = open(gcodeFilePath, 'r')
    
    listOfParsedLayers = []
    
    gcodePattern = re.compile("(\s*G[01](?:\s+[XYZEF](?:[-+]?(?:\d*\.\d+|\d+)))+\s*)(?:;(.*))?$") #Pattern that matches G0 or G1 commands. To be noted, I don't see any G0 commansd in Prusa Slicer.
    nonMovingGcodePattern = re.compile("\s*G[01](\s+[EF](?:[-+]?(?:\d*\.\d+|\d+)))+\s*$") #Matches the G0 or G1 commands that have no X,Y or Z components, thereby are not travel moves.
    layerChangePattern = re.compile("\s*;LAYER_CHANGE\s*") #Detecting Layer change, I think this makes things incompatible with vase mode.
    widthPattern = re.compile("\s*;WIDTH:([0-9]+(?:\.[0-9]+)?)\s*$") #Detecting a change in the width of print line
    zPosPattern = re.compile("\s*;Z:([0-9]+(?:\.[0-9]+)?)\s*$")
    heightPattern = re.compile("\s*;HEIGHT:([0-9]+(?:\.[0-9]+)?)\s*$")
    typePattern = re.compile("\s*;TYPE:(.*)$")
    firstPointPattern = re.compile("move to first")

    prevLayerGcodes = [] #All GCodes that move the nozzle, with our without extrusion would be stored here and then popped when the next later starts
    prevLayerZPos = 0 #Prusa Slicer Prints the Z position and layer height after each layer change
    prevLayerHeight = 0
    curLineNumber = 0 #For error tracing
    curLayerNumber = 0

    valueTacker = {'X':0, 'Y':0, 'Z':0, 'E':0, 'W':0.5, 'layerNumber':0, 'type':'Custom'} #E is extrusion; X, Y and Z are the coordinates; W is width of the  print line

    precision = getFromParam('precision',params)
    while True:
        line = file.readline()
        curLineNumber = curLineNumber + 1
        
        
        if bool(layerChangePattern.match(line)):
            zPos = 0
            height = 0

            try:
                line = file.readline()
                curLineNumber = curLineNumber + 1
                zPos = float(zPosPattern.search(line)[1])
            except (IndexError, TypeError):
                raise NoZPosMatch(line, curLineNumber)

            try:
                line = file.readline()
                curLineNumber = curLineNumber + 1
                height = float(heightPattern.search(line)[1])

            except (IndexError, TypeError):
                raise NoHeightMatch(line, curLineNumber)


            prevLayer = Layer(prevLayerZPos, prevLayerHeight, curLayerNumber, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)

            
            prevLayerGcodes = []
            prevLayerZPos = zPos
            prevLayerHeight = height
            curLayerNumber = curLayerNumber + 1

            

        elif bool(widthPattern.match(line)):
            valueTacker['W'] = round(float(widthPattern.search(line)[1]), precision)

        elif bool(typePattern.match(line)):
            valueTacker['type'] = typePattern.search(line)[1].strip()
            
        elif bool(gcodePattern.match(line)):
            
            gcodePart = gcodePattern.search(line)[1].strip()
            commentPart = ""

            try:
                commentPart = gcodePattern.search(line)[2].strip()
            except (IndexError, AttributeError):
                pass

            separatedGcode = gcodePart.split()
            tempDict = valueTacker.copy()
            
            if not bool(nonMovingGcodePattern.match(gcodePart)):
                
                for term in separatedGcode:
                    tempDict[term[0]] = float(term[1:])
                    if term[0] in ['X', 'Y', 'Z']:
                        valueTacker[term[0]] = float(term[1:])
                tempDict['lineNumber'] = curLineNumber
                
                prevLayerGcodes.append(tempDict.copy())
            
            
        

        elif not line:
            prevLayer = Layer(prevLayerZPos, prevLayerHeight, curLayerNumber, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)
            break

        else:
            pass
    
    return listOfParsedLayers

#Take the parsed GCode and finally make it into a curve that is beveled on blender
def placeCurve(coords, width, height, zPos, type, bevelSuffix, collection, params):
    
    widthOffset = getFromParam('widthOffset',params)
    heightOffset = getFromParam('heightOffset',params)
    precision = getFromParam('precision',params)

    if (len(coords) > 1):
        #print("Curve placed")
        curveData = bpy.data.curves.new('myCurve', type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 1
        curveData.render_resolution_u = 12

        polyline = curveData.splines.new('BEZIER')
        polyline.bezier_points.add(len(coords)-1)
        bevelObject = None
        for i, coord in enumerate(coords):
            x,y,z = coord
            polyline.bezier_points[i].co = (x, y, z)
            polyline.bezier_points[i].handle_left = (x, y, z)
            polyline.bezier_points[i].handle_right = (x, y, z)

        view_layer = bpy.context.view_layer
        curveOB = bpy.data.objects.new('myCurve', curveData)
        #curveOB.data.bevel_depth = 0.1
        curveOB.data["zPos"] = zPos
        curveOB.data["type"] = type

        bevelName = ("{:."+str(precision)+"f}").format(width + widthOffset) + "_" + ("{:."+str(precision)+"f}").format(height + heightOffset) + "_" + bevelSuffix

        if bevelName in bpy.data.objects.keys():
            bevelObject = bpy.data.objects.get(bevelName)
        else:
            createProfile(width+widthOffset, height+heightOffset, bevelName)
            bevelObject = bpy.data.objects.get(bevelName)
        
        curveData.bevel_mode = "OBJECT" 
        curveData.bevel_object = bpy.data.objects.get(bevelName)
        curveData.use_fill_caps = True

        ## Delte after testing
        mat = bpy.data.materials.get("Material.001")
        curveOB.data.materials.append(mat)
        curveOB.modifiers.new('split', 'EDGE_SPLIT')
        curveOB.modifiers.get('split').show_viewport = False
        ## Delte after testing        
        curveOB.hide_viewport = True
        collection.objects.link(curveOB)
        
        return curveOB

def toggleVisibility(filters):
    listOfCurves = bpy.context.scene['typeDictionary']

    for key in filters.keys():
        if ( key in listOfCurves.keys()):
            if (filters[key]):
                for obj in listOfCurves[key]:
                    obj.hide_viewport = False
            else:
                for obj in listOfCurves[key]:
                    obj.hide_viewport = True


defaultParams = { 'widthOffset':0, 'heightOffset':0, 'precision': 2 }
def getFromParam(key, params):
    if key in params.keys():
        return params[key]
    elif key in defaultParams:
        return defaultParams[key]

    else:
        raise NoSuchPropertyException(key)

def builder(gcodeFilePath, objectName="OBJECT", bevelSuffix="bevel", params = {}, filters = {}):
    
    listOfParsedLayers = gcodeParser(gcodeFilePath, params)
    typeDictionary = {}

    i = 0
    
    parentCollection =  bpy.data.collections.new(objectName)
    bpy.context.scene.collection.children.link(parentCollection)

    for currentLayer in listOfParsedLayers:
        prevWidth = 0
        prevType = "Custom"
        coords = []

        layerCollection = bpy.data.collections.new("Layer " + str(currentLayer.layerNumber))
        parentCollection.children.link(layerCollection)
        #currentLayer.gcodes = filter(lambda x: 67870 < x['lineNumber'] and x['lineNumber'] <= 67966 ,currentLayer.gcodes)
        
        placeCurveAnonFunc = lambda : placeCurve(coords, prevWidth, currentLayer.height, currentLayer.zPos, prevType, bevelSuffix, layerCollection, params)
        def appendToTypeDict(curve, type):
            type = re.sub(" |/","_", type) 
            if (not curve == None):
                if type in typeDictionary.keys():
                    typeDictionary[type].append(curve)
                else: 
                    typeDictionary.update({type: []})
                    typeDictionary[type].append(curve)

        for elem in currentLayer.gcodes:
            #print(elem)
            if (elem["E"] > 0):
                if (elem['W'] == prevWidth and elem['type'] == prevType):
                    coords.append((elem['X'],elem['Y'],elem['Z']))
                else:
                    curveOB = placeCurveAnonFunc()
                    appendToTypeDict(curveOB, prevType)
                    prevWidth = elem['W']
                    prevType = elem['type']
                    coords = coords[-1:]
                    coords.append((elem['X'],elem['Y'],elem['Z']))
                
            else:
                
                curveOB = placeCurveAnonFunc()
                appendToTypeDict(curveOB, prevType)
                
                coords = [(elem['X'],elem['Y'],elem['Z'])]

            
        curveOB = placeCurveAnonFunc()
        appendToTypeDict(curveOB, prevType)
        i = i + 1


    ## Felt experimental might delete later
    bpy.context.scene['typeDictionary'] = typeDictionary
    
    toggleVisibility(filters)
    
            


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