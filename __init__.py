from pickle import TRUE
from pydoc import describe
from random import seed
import io
import re
import time
import bpy
import sys
import os

bl_info = {
    'name': 'Stitch3r - GCode Renderer',
    'blender': (3, 0, 1),
    'category': 'Object',
    'location': "View3D > Tools > MyPlugin",
    'version': (1, 0, 0),
    'author': 'Vipul Rajan',
    'description': 'An example addon',
}

modulesNames = ['Constants', 'ExtruderErrorCreator', 'Exceptions', 'EndPointCreator',
                'BevelShapeCreator', 'GCodeReader', 'Meshifier', 'GCodeLoaderOperator']

modulesFullNames = {}
for currentModuleName in modulesNames:
    modulesFullNames[currentModuleName] = (
        '{}.{}'.format(__name__, currentModuleName))

for currentModuleFullName in modulesFullNames.values():
    import importlib
    if currentModuleFullName in sys.modules:
        importlib.reload(sys.modules[currentModuleFullName])
    else:
        globals()[currentModuleFullName] = importlib.import_module(
            currentModuleFullName)
        setattr(globals()[currentModuleFullName],
                'modulesNames', modulesFullNames)

ParamNames = sys.modules[modulesFullNames['Constants']].ParamNames
Keywords = sys.modules[modulesFullNames['Constants']].Keywords
propsNonAnimatable = sys.modules[modulesFullNames['Constants']
                                 ].propsNonAnimatable
getFilamentName = sys.modules[modulesFullNames['Constants']].getFilamentName
Patterns = sys.modules[modulesFullNames['Constants']].Patterns
GCodeReader = sys.modules[modulesFullNames['GCodeReader']]
GCodeLoaderOperatorModule = sys.modules[modulesFullNames['GCodeLoaderOperator']]


GCodeLoaderOperator = GCodeLoaderOperatorModule.GCodeLoaderOperator


class AssetLoaderOperator(bpy.types.Operator):

    bl_idname = 'opr.asset_loader'
    bl_label = 'Load Assets'
    bl_description = "Load the plate, backdrop and camera and lighting"

    def execute(self, context):
        filepath = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.collections = [Keywords.importCollectionName]

        for col in data_to.collections:
            if col is not None:
                bpy.context.scene.collection.children.link(col)
        return {'FINISHED'}


class ExternalPerimeterSelector(bpy.types.Operator):

    bl_idname = 'opr.external_perimeter_selector'
    bl_label = 'Load Assets'

    def execute(self, context):
        seed = 237
        probability = getattr(
            bpy.context.scene.Stitcher_Props, 'ExtruderError_Probability')

        sys.modules[modulesFullNames['ExtruderErrorCreator']].makeSelection(
            bpy.context.scene["Stitcher_Object_Collection"], probability, seed)
        return {'FINISHED'}


class GeometryNodesApplicator(bpy.types.Operator):

    bl_idname = 'opr.geometry_nodes_applicator'
    bl_label = 'Load Assets'

    def execute(self, context):
        sys.modules[modulesFullNames['ExtruderErrorCreator']].applyGeoNodes()
        return {'FINISHED'}


class PanelParent(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Stitch3r"


class Options(PanelParent):
    bl_idname = 'VIEW3D_PT_panel_options'
    bl_label = 'Options'

    def draw(self, context):
        col = self.layout.column()
        for propName in propsMain:
            row = col.row()
            row.prop(context.scene.Stitcher_Props, propName)

        row = col.row()
        col.operator('opr.gcode_loader', text='Load GCode')

        row = col.row()
        col.operator('opr.asset_loader', text='Load Assets')

        row = col.row()
        col.operator('opr.meshifier')

        row = col.row()
        row.label(text=context.scene.Stitcher_Props.Status)


class Animatable(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_options"
    bl_idname = 'VIEW3D_PT_panel_animatable'
    bl_label = "Animatable"

    def draw(self, context):
        col = self.layout.column()
        for propName in propsAnimatable:
            row = col.row()
            row.prop(context.scene.Stitcher_Props, propName)


class NonAnimatable(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_options"
    bl_idname = 'VIEW3D_PT_panel_nonanimatable'
    bl_label = "Non-Animatable"

    # ('Extruder Error',('ExtruderError_Density', 'Density'),('ExtruderError_Probability', 'Probability'))
    def draw(self, context):
        col = self.layout.column()
        for propGroup in propsNonAnimatable:

            if (isinstance(propGroup, str)):
                row = col.row()
                row.prop(context.scene.Stitcher_Props, propGroup)
            elif (isinstance(propGroup, tuple)):
                row = col.row()
                row.label(text=propGroup[0]+":")
                row = col.row()
                for prop in propGroup[1:]:
                    row.prop(context.scene.Stitcher_Props,
                             prop[0], text=prop[1])

        row = col.row()
        row.label(text="Extruder Error")
        row = col.row()
        row.prop(context.scene.Stitcher_Props,
                 'ExtruderError_Probability', text='Probability')
        row.operator('opr.external_perimeter_selector', text='Make Selection')

        row = col.row()
        row.prop(context.scene.Stitcher_Props,
                 'ExtruderError_Density', text='Density')
        row.operator('opr.geometry_nodes_applicator', text='Apply Errors')
        row.enabled = bool(len(context.selected_objects))


class TypeFilters(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_options"
    bl_idname = 'VIEW3D_PT_panel_type_filters'
    bl_label = "Type Filters"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column()
        # row = col.row()
        # row.prop(context.scene.Stitcher_Props, 'ViewportOnly')
        row = col.row()
        row.label(text="Features:")
        for propKeyValue in context.scene.Stitcher_Props.TypesFiltersMap:
            row = col.row()
            row.prop(propKeyValue, "value", text=propKeyValue.key)


def showPopup(message, title, icon):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


class KeyValueType(bpy.types.PropertyGroup):
    key: bpy.props.StringProperty(name="Key")
    value: bpy.props.BoolProperty(name="Value")


def fileNameUpdationFunction(self, context):
    context.scene.Stitcher_Props.Loading_Ready = False
    self.Status = "Preprocessing the File"
    startTime = time.time()

    filename, file_extension = os.path.splitext(self.FilePath)

    if file_extension == '.gcode':
        file = open(self.FilePath, 'r')
        print(self.FilePath)

        fi = io.FileIO(file.fileno())
        fb = io.BufferedReader(fi)

        typesSet = set()
        filamentSet = set()
        line = fb.readline()

        typePattern = Patterns.printerSpecificPatterns['orca']['typePattern']
        filamentChangePattern = Patterns.printerSpecificPatterns['orca']['filamentChangePattern']
        curveGcodePattern = Patterns.curveGcodePattern
        g2g3Found = False

        while line:
            line = line.decode().strip()
            if bool(typePattern.match(line)):
                curveType = typePattern.search(line)[1].strip()
                subbedType = re.sub(" |/", "_", curveType)
                typesSet.add(subbedType)

            if bool(filamentChangePattern.match(line)):
                filamentNumber = int(
                    filamentChangePattern.search(line)[1].strip())
                filamentSet.add(filamentNumber)

            if bool(curveGcodePattern.match(line)):
                g2g3Found = True
                break

            line = fb.readline()

        file.close()

        self.TypesFiltersMap.clear()
        self.TypesFiltersDict.clear()

        for idx, item in enumerate(typesSet):
            temp = self.TypesFiltersMap.add()
            temp.key = item
            temp.value = True

            self.TypesFiltersDict[item] = idx

        self.materials.clear()

        if bpy.data.materials.get(Keywords.materialName) == None:
            filepath = os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "assets.blend")
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                data_to.materials = [Keywords.materialName]

            mat = bpy.data.materials.get(Keywords.materialName).copy()
            mat.name = getFilamentName(Keywords.materialName, 0)

        self.materials.append(getFilamentName(Keywords.materialName, 0))

        for filamentNumber in filamentSet:
            if filamentNumber != 0 and bpy.data.materials.get(getFilamentName(Keywords.materialName, filamentNumber)) == None:
                mat = bpy.data.materials.get(Keywords.materialName).copy()
                mat.name = getFilamentName(
                    Keywords.materialName, filamentNumber)

            if filamentNumber != 0:
                self.materials.append(getFilamentName(
                    Keywords.materialName, filamentNumber))

        endTime = time.time()
        timeTaken = int(endTime - startTime)

        context.scene.Stitcher_Props.Loading_Ready = not g2g3Found

        if g2g3Found:
            showPopup(
                "Err 33: File contains G2/G3 GCode Commands. Please turn off 'Arc Fitting' in slicer settings",
                "Invalid GCode", "ERROR")
            self.Status = "File contains G2/G3. Please Turn off Arc Fitting"

        else:
            self.Status = "File Preprocessing Done: took {}s".format(timeTaken)

    else:
        showPopup(
            "Err 34: Please provide a valid GCode File with .gcode extension",
            "Invalid File", "ERROR")
        self.Status = "Invalid File"


class Stitcher_Props(bpy.types.PropertyGroup):

    ObjectName: bpy.props.StringProperty(
        name='Object Name', description='What to name the imported object collection', default='OBJECT')
    BevelName: bpy.props.StringProperty(
        name='Bevel Name', description='What to name the created bevel profiles', default='bevel')
    FilePath: bpy.props.StringProperty(
        name='File Path', description="Path of GCode file", subtype="FILE_PATH", update=fileNameUpdationFunction)

    SeamAbberation_Amount: bpy.props.FloatProperty(
        name='Seam Abberation Distance', default=0, description='The maximum amount to vary the seams', min=0)
    SeamAbberation_Probability: bpy.props.FloatProperty(
        name='Seam Abberation Probability', default=0, description='The probability with which a seam would be picked to be varied.\n0 being none and 1 being all', min=0, max=100)

    WidthOffset: bpy.props.FloatProperty(
        name='Width Offset', default=0, description='All the lines widths would be offset by this amount', min=-1, max=1)
    HeightOffset: bpy.props.FloatProperty(
        name='Height Offset', default=0, description='All the lines heights would be offset by this amount ', min=-1, max=1)
    Precision: bpy.props.IntProperty(
        name='Precision', description="What decimal place to round off the GCode Coordinates to", default=4, min=2, max=10)
    ExtruderError_Density: bpy.props.FloatProperty(
        name='Extruder Error Density', default=0.1, description='The density of extruder mistakes', min=0.00, max=1.00, step=0.05)
    ExtruderError_Probability: bpy.props.FloatProperty(
        name='Extruder Error Probability', default=0, description='The probability with which a point would be picked to be varied.\n0 being none and 1 being all', min=0)
    MergeAngle: bpy.props.FloatProperty(
        name='Merge Angle', default=3, description='The minimum angle in degrees on which to merge two lines', min=0, step=1)

    TypesFiltersMap: bpy.props.CollectionProperty(type=KeyValueType)
    TypesFiltersDict = {}
    materials = []

    Loading_Ready: bpy.props.BoolProperty(
        name='Loading Ready', description="Gcode File Can Be Loaded", default=False)

    End_Point: bpy.props.BoolProperty(name='End Point', default=True)
    Extruder_Error: bpy.props.BoolProperty(name='Extruder Error', default=True)

    SeamDistance: bpy.props.FloatProperty(
        name='Seam Distance', default=0.2, description='How far apart should the seams be to get a desired look', min=0)
    LayerIndexTop: bpy.props.IntProperty(
        name='Layer Index', default=5000, description='The topmost layer to show, every layer after this would be hidden', min=0)

    DegreesPerJointPoint: bpy.props.IntProperty(
        name='Desgrees Per Joint Point', default=36, description='Lower number will put more points on end points and curved joints', min=3, max=90)

    Status: bpy.props.StringProperty(
        name='Status', description='Processing Status', default='Not Processing')

    def get_filter_value(self, key):
        for item in self.TypesFiltersMap:
            if item.key == key:
                return item.value

    def get_filter_index(self, key):
        for idx, item in enumerate(self.TypesFiltersMap):
            if item.key == key:
                return idx


CLASSES = [
    KeyValueType, Stitcher_Props, Options, TypeFilters, GCodeLoaderOperator, Animatable, AssetLoaderOperator, NonAnimatable, ExternalPerimeterSelector, GeometryNodesApplicator,
]

propsMain = [
    'ObjectName', 'BevelName', 'FilePath'
]

propsAnimatable = ['LayerIndexTop']


def register():
    print('registered')  # just for debug
    for klass in CLASSES:
        bpy.utils.register_class(klass)

    bpy.types.Scene.Stitcher_Props = bpy.props.PointerProperty(
        type=Stitcher_Props)


def unregister():
    print('unregistered')  # just for debug
    for klass in CLASSES:
        bpy.utils.unregister_class(klass)

    del bpy.types.Scene.Stitcher_Props


if __name__ == '__main__':
    register()
