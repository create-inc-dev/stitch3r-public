from ast import Param
import bpy
import sys
import math
import re

from numpy import var 


moduleParentName = '.'.join(__name__.split('.')[:-1])
createProfile = sys.modules[moduleParentName + '.BevelShapeCreator'].createProfile
NoZPosMatch = sys.modules[moduleParentName + '.Exceptions'].NoZPosMatch
NoHeightMatch = sys.modules[moduleParentName + '.Exceptions'].NoHeightMatch
NoSuchPropertyException = sys.modules[moduleParentName + '.Exceptions'].NoSuchPropertyException
createEndPoints = sys.modules[moduleParentName + '.EndPointCreator'].createEndPoints
ImproperCruveException = sys.modules[moduleParentName + '.Exceptions'].ImproperCruveException

ParamNames = sys.modules[moduleParentName + '.Constants'].ParamNames
Coin = sys.modules[moduleParentName + '.Constants'].BiasedCoin
Keywords = sys.modules[moduleParentName + '.Constants'].Keywords

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

    print(__file__)
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

    valueTacker = {'X':0, 'Y':0, 'Z':0, 'E':0, 'W':0.5, 'H':0.2, 'layerNumber':0, 'type':'Custom'} #E is extrusion; X, Y and Z are the coordinates; W is width of the  print line

    precision = params[ParamNames.precision]
    while True:
        line = file.readline()
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
            
            #Ignore any GCode G0/G1 command that doesn't move the extruder
            if not bool(nonMovingGcodePattern.match(gcodePart)):
                
                for term in separatedGcode:
                    tempDict[term[0]] = float(term[1:])
                    if term[0] in ['X', 'Y', 'Z']:
                        valueTacker[term[0]] = float(term[1:])
                tempDict['lineNumber'] = curLineNumber
                
                prevLayerGcodes.append(tempDict.copy())
        
        #In case of layer change, push the accumulated GCodes of previous layer and start accumulating the next one.
        elif bool(layerChangePattern.match(line)):  
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
                valueTacker['H'] = height
                
            except (IndexError, TypeError):
                raise NoHeightMatch(line, curLineNumber)


            prevLayer = Layer(prevLayerZPos, prevLayerHeight, curLayerNumber, prevLayerGcodes)
            listOfParsedLayers.append(prevLayer)

            
            prevLayerGcodes = []
            prevLayerZPos = zPos
            prevLayerHeight = height
            curLayerNumber = curLayerNumber + 1

            
        elif bool(heightPattern.match(line)):
            valueTacker['H'] = round(float(heightPattern.search(line)[1]), precision)

        elif bool(widthPattern.match(line)):
            valueTacker['W'] = round(float(widthPattern.search(line)[1]), precision)

        elif bool(typePattern.match(line)):
            curveType = typePattern.search(line)[1].strip()
            valueTacker['type'] = re.sub(" |/","_", curveType)
            
        elif not line:
            prevLayer = Layer(prevLayerZPos, prevLayerHeight, curLayerNumber, prevLayerGcodes)
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
    var0.targets[0].data_path = "Buddy_Props.LayerIndexTop"

    var1 = driver.variables.new()
    var1.name = "var1"
    var1.targets[0].id_type = 'SCENE'
    var1.targets[0].id = bpy.context.scene
    var1.targets[0].data_path = "Buddy_Props." + curveType

    var2 = driver.variables.new()
    var2.name = "var2"
    var2.targets[0].id = curveOB
    var2.targets[0].data_path = '["layerNumber"]'

    
    condition1 = var1.name                                   #is the curve type checked in the visibility tab
    condition2 = "({0} <= {1})".format(var2.name, var0.name) #is the layer suppored to be visible i.e. layer number <= layer top index
    condition3 = "True"                                      #is the parent visible
    
    if (drivenProperty == "hide_render"):
        var4 = driver.variables.new()
        var4.name = "var4"
        var4.targets[0].id_type = 'SCENE'
        var4.targets[0].id = bpy.context.scene
        var4.targets[0].data_path = "Buddy_Props.ViewportOnly"
        
        condition1 = "({0} or {1})".format(var1.name, var4.name)

    ##The rounded starting and end points would have a parent parameter that points to the curve they are placed on.
    ##It's import to tie their visbility to their parent
    if ('parent' in curveOB.keys()):
        var3 = driver.variables.new()
        var3.name = "var3"
        var3.targets[0].id = curveOB['parent']
        var3.targets[0].data_path = drivenProperty

        condition3 = "not ("+ var3.name +")"
        
    driver.expression = "not ({0} and {1} and {2})".format(condition1, condition2, condition3)

    








#Take the parsed GCode and finally make it into a curve that is beveled on blender
def placeCurve(coords, width, height, zPos, curveType, layerNumber, bevelSuffix, collection, params):
    
    widthOffset = params[ParamNames.widthOffset]
    heightOffset = params[ParamNames.heightOffset]
    precision = params[ParamNames.precision]

    lengthOfCurve = 0

    if (len(coords) > 1):
        
        #Create new curve data and set it's properties
        #Dimensions are set to 3D because setting it to 2D produces weird bugs and artefacts
        curveData = bpy.data.curves.new('myCurve', type='CURVE')
        curveData.dimensions = '3D'
        curveData.resolution_u = 1
        curveData.render_resolution_u = 12

        #It's not a polyline curve, it's a bezier curve being edited to emulate a polyline curve.
        #A polyline curve was giving uneven thickness when beveled
        polyline = curveData.splines.new('BEZIER')
        polyline.bezier_points.add(len(coords)-1)
        bevelObject = None
        prevCoord = coords[0]

        for i, coord in enumerate(coords):
            x,y,z = coord
            polyline.bezier_points[i].co = (x, y, z)
            polyline.bezier_points[i].handle_left = (x, y, z)
            polyline.bezier_points[i].handle_right = (x, y, z)

            lengthOfCurve = lengthOfCurve + math.dist(prevCoord, coord)
            prevCoord = coord

        
        curveOB = bpy.data.objects.new('myCurve', curveData)
        
        #Properties for debugging and other uses
        curveOB.data["zPos"] = zPos
        curveOB["zPos"] = zPos

        curveOB.data["type"] = curveType
        curveOB["type"] = curveType

        curveOB.data["lengthOfCurve"] = lengthOfCurve

        curveOB.data["layerNumber"] = layerNumber
        curveOB["layerNumber"] = layerNumber
        curveOB.hide_viewport = True



        bevelName = ("{:."+str(precision)+"f}").format(width + widthOffset) + "_" + ("{:."+str(precision)+"f}").format(height + heightOffset) + "_" + bevelSuffix

        if bevelName in bpy.data.objects.keys():
            bevelObject = bpy.data.objects.get(bevelName)
        else:
            createProfile(width+widthOffset, height+heightOffset, 1, bevelName)
            bevelObject = bpy.data.objects.get(bevelName)
        
        curveData.bevel_mode = "OBJECT" 
        curveData.bevel_object = bpy.data.objects.get(bevelName)
        curveData.use_fill_caps = True

    
        #Material was already imported from assets.blend file when the "Load GCode" button was pressed
        mat = bpy.data.materials.get(Keywords.materialName)
        if (len(curveOB.data.materials) == 0):
            curveOB.data.materials.append(mat)
          

        #Aplly modifier to smooth out overlap artefacts, only shows in renders
        curveOB.modifiers.new('split', 'EDGE_SPLIT')
        curveOB.modifiers.get('split').show_viewport = False

        #Change bevel mapping - this would be used for rounding the end points of the curve
        curveOB.data.bevel_factor_mapping_start = 'SPLINE'
        curveOB.data.bevel_factor_mapping_end = 'SPLINE'

        
        collection.objects.link(curveOB)
        
        return curveOB


def builder(gcodeFilePath, objectName="OBJECT", bevelSuffix="bevel", params = {}):
    
    #print(params)
    coin = Coin(params[ParamNames.seed])

    listOfParsedLayers = gcodeParser(gcodeFilePath, params)


    i = 0
    
    parentCollection =  bpy.data.collections.new(objectName)
    bpy.context.scene.collection.children.link(parentCollection)

    for currentLayer in listOfParsedLayers[0:20]:
        
        prevWidth = 0
        prevType = "Custom"
        prevHeight = 0
        coords = []

        
        layerCollection = bpy.data.collections.new("Layer " + str(currentLayer.layerNumber))
        parentCollection.children.link(layerCollection)

        #Below line is used for debugging particular lines of gcode
        #currentLayer.gcodes = filter(lambda x: 73 < x['lineNumber'] and x['lineNumber'] <= 93 ,currentLayer.gcodes)
        
        

        def placeCurveFunc(curveType):
            
            curveOB = placeCurve(coords, prevWidth, prevHeight, currentLayer.zPos, prevType, currentLayer.layerNumber, bevelSuffix, layerCollection, params)
            if (not curveOB == None):
                addVisibilityDriver(curveOB, "hide_viewport")
                addVisibilityDriver(curveOB, "hide_render")
            

            if (curveType in ["External_perimeter", "Skirt_Brim", "Perimeter", "Top_solid_infill", "Overhang_perimeter"] and not curveOB == None ):
                endPoint, startPoint = createEndPoints(curveOB, params, coin)
                layerCollection.objects.link(endPoint)
                layerCollection.objects.link(startPoint)
                
                addVisibilityDriver(endPoint, "hide_viewport")
                addVisibilityDriver(startPoint, "hide_viewport")
                addVisibilityDriver(endPoint, "hide_render")
                addVisibilityDriver(startPoint, "hide_render")

        for elem in currentLayer.gcodes:
            #print(elem)
            if (elem["E"] > 0):
                if (elem['W'] == prevWidth and elem['type'] == prevType and elem['H'] == prevHeight):
                    coords.append((elem['X'],elem['Y'],elem['Z']))
                else:
                    placeCurveFunc(prevType)
            
                    prevWidth = elem['W']
                    prevType = elem['type']
                    prevHeight = elem['H']

                    coords = coords[-1:]
                    coords.append((elem['X'],elem['Y'],elem['Z']))
                
            else:
                
                placeCurveFunc(prevType)
                coords = [(elem['X'],elem['Y'],elem['Z'])]

            
        placeCurveFunc(prevType)

        print("Layer Done: " + str(currentLayer.layerNumber), end='\r', flush=True)
        i = i + 1
    
    bpy.context.scene["Buddy_Object_Collection"] = parentCollection