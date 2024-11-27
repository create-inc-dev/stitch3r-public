import sys
import bpy
import time
import os
from mathutils import Vector

moduleParentName = '.'.join(__name__.split('.')[:-1])
modulesNames = ['Constants', 'ExtruderErrorCreator', 'Exceptions',
                'EndPointCreator', 'BevelShapeCreator', 'GCodeReader', 'Meshifier']

modulesFullNames = {}
for currentModuleName in modulesNames:
    modulesFullNames[currentModuleName] = (
        '{}.{}'.format(moduleParentName, currentModuleName))

ParamNames = sys.modules[modulesFullNames['Constants']].ParamNames
Keywords = sys.modules[modulesFullNames['Constants']].Keywords
propsNonAnimatable = sys.modules[modulesFullNames['Constants']
                                 ].propsNonAnimatable
GCodeReader = sys.modules[modulesFullNames['GCodeReader']]


def appendIfLongEnough(coords, newElem):

    if (len(coords) == 0):
        coords.append({"point": (newElem['X'], newElem['Y'], newElem['Z']),
                       "width": newElem['W'],
                       "height": newElem['H']})
    else:
        lastCoord = coords[-1]
        lastPoint = Vector(lastCoord["point"])
        newPoint = Vector((newElem['X'], newElem['Y'], newElem['Z']))
        distance = (lastPoint - newPoint).length

        if (True):
            coords.append({"point": (newElem['X'], newElem['Y'], newElem['Z']),
                           "width": newElem['W'],
                           "height": newElem['H']})


class GCodeLoaderOperator(bpy.types.Operator):

    bl_idname = 'opr.gcode_loader'
    bl_label = 'Load GCode'
    bl_description = "Load the GCode and construct the model"

    @classmethod
    def poll(cls, context):
        return context.scene.Stitcher_Props.FilePath is not None and len(context.scene.Stitcher_Props.FilePath) > 0 and context.scene.Stitcher_Props.Loading_Ready

    def modal(self, context, event):
        if self.state == 2:
            self.endTime = time.time()

            timeTaken = int(self.endTime - self.startTime)

            parentObj = self.params[ParamNames.parent]

            try:
                parentDrivers = parentObj.animation_data.drivers

                for driver in parentDrivers:
                    if driver.data_path.startswith('["' + Keywords.maxZHeight):
                        driver.driver.expression += " "
                        driver.driver.expression = driver.driver.expression[:-1]
            except AttributeError:
                pass

            bpy.context.scene["Stitcher_Object_Collection"] = self.parentCollection
            bpy.context.scene.Stitcher_Props.Status = "Processing Done took {}s".format(
                timeTaken)
            return {'FINISHED'}

        elif self.state == 0:
            self.coin = sys.modules[modulesFullNames['Constants']].BiasedCoin(
                self.params[ParamNames.seed])

            self.objectName = getattr(
                bpy.context.scene.Stitcher_Props, 'ObjectName')

            i = 0

            self.parentCollection = bpy.data.collections.new(self.objectName)
            bpy.context.scene.collection.children.link(self.parentCollection)
            if not self.params[ParamNames.parent]:
                newEmpty = bpy.data.objects.new("empty", None)
                self.parentCollection.objects.link(newEmpty)
                newEmpty.empty_display_size = 50
                newEmpty.empty_display_type = 'PLAIN_AXES'
                self.params[ParamNames.parent] = newEmpty

            self.numberOfLayers = len(self.listOfParsedLayers) - 1

            parentObj = self.params[ParamNames.parent]
            parentObj[Keywords.numberOfLayers] = self.numberOfLayers
            parentObj[Keywords.overrideHeight] = False
            parentObj[Keywords.overrideHeightValue] = 0.000
            parentObj[Keywords.layerHeight] = [
                0 for i in range(self.numberOfLayers + 1)]
            self.state = 1

            self.report({'INFO'}, 'GCode Parsed Successfully')
            bpy.context.scene.Stitcher_Props.Status = "GCode Parsed Successfully"
            return {'RUNNING_MODAL'}

        elif self.state == 1:
            try:
                currentLayer = self.listOfParsedLayers.pop(0)
            except IndexError:
                self.state = 2
                return {'RUNNING_MODAL'}

            prevWidth = 0
            prevType = "Custom"
            prevHeight = 0
            prevFilament = 0
            coords = []

            curvesToPlace = []

            widthOffset = self.params[ParamNames.widthOffset]
            heightOffset = self.params[ParamNames.heightOffset]

            for elem in currentLayer.gcodes:

                visibilityPropertyIndex = bpy.context.scene.Stitcher_Props.TypesFiltersDict[
                    elem['type']]
                isTypeVisible = bpy.context.scene.Stitcher_Props.TypesFiltersMap[
                    visibilityPropertyIndex].value

                if (elem["E"] > 0 and isTypeVisible):
                    if (elem['filament'] == prevFilament):

                        coords.append({"point": (elem['X'], elem['Y'], elem['Z']),
                                       "width": elem['W'] + widthOffset,
                                       "height": elem['H'] + heightOffset})
                    else:
                        curvesToPlace.append({"coords": coords,
                                              "type": prevType,
                                              "filament": prevFilament})

                        prevType = elem['type']
                        prevFilament = elem['filament']

                        coords = coords[-1:]
                        coords.append({"point": (elem['X'], elem['Y'], elem['Z']),
                                       "width": elem['W'] + widthOffset,
                                       "height": elem['H'] + heightOffset})

                else:
                    curvesToPlace.append({"coords": coords,
                                          "type": prevType,
                                          "filament": prevFilament})

                    coords = [{"point": (elem['X'], elem['Y'], elem['Z']),
                               "width": None,
                               "height": None}]

            curvesToPlace.append({"coords": coords,
                                  "filament": prevFilament})

            GCodeReader.placeLayer(curvesToPlace, currentLayer.zPos,
                                   currentLayer.layerNumber, self.parentCollection, self.coin, self.params)

            bpy.context.scene.Stitcher_Props.Status = "Layer Done: {}/{}".format(
                currentLayer.layerNumber, self.numberOfLayers)
            print("Layer Done: {}/{}".format(currentLayer.layerNumber,
                  self.numberOfLayers))
            self.report(
                {'INFO'}, "Layer Done: {}/{}".format(currentLayer.layerNumber, self.numberOfLayers))

            return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.startTime = time.time()
        fileName: bpy.props.StringProperty = getattr(
            bpy.context.scene.Stitcher_Props, 'FilePath')

        params = {}
        for propGroup in propsNonAnimatable:

            if (isinstance(propGroup, str)):
                params[propGroup] = getattr(
                    bpy.context.scene.Stitcher_Props, propGroup)
            elif (isinstance(propGroup, tuple)):
                params[propGroup[0]] = {}
                for prop in propGroup[1:]:
                    params[propGroup[0]][prop[1]] = getattr(
                        bpy.context.scene.Stitcher_Props, prop[0])

        params[ParamNames.seed] = 237
        params[ParamNames.slicer] = getattr(
            bpy.context.scene.Stitcher_Props, "SlicerType")
        params[ParamNames.parent] = getattr(
            bpy.context.scene.Stitcher_Props, "ParentObject")

        if not bpy.data.node_groups.get(Keywords.geoNodesName):
            filepath = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "assets.blend")
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                data_to.node_groups = [Keywords.geoNodesName]

            bpy.data.node_groups.get(
                Keywords.geoNodesName).use_fake_user = True

        self.fileName = fileName
        self.params = params
        self.state = 0
        self.i = 0
        self.listOfParsedLayers = GCodeReader.gcodeParser(
            self.fileName, self.params)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
