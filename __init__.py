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
    'blender': (4, 2, 0),
    'category': 'Object',
    'location': "View3D > Tools > MyPlugin",
    'version': (2, 1, 5),
    'author': 'Vipul Rajan',
    'description': 'GCode Visualizer Tool',
}

modulesNames = ['Constants', 'ExtruderErrorCreator', 'Exceptions', 'CurveGCodeProcessor', 'EndPointCreator',
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
slicerItems = sys.modules[modulesFullNames['Constants']].slicerItems
Patterns = sys.modules[modulesFullNames['Constants']].Patterns
patternMatcherFunction = sys.modules[modulesFullNames['Constants']
                                     ].patternMatcherFunction
patternMatcherSearch = sys.modules[modulesFullNames['Constants']
                                   ].patternMatcherSearch
GCodeReader = sys.modules[modulesFullNames['GCodeReader']]
GCodeLoaderOperatorModule = sys.modules[modulesFullNames['GCodeLoaderOperator']]


GCodeLoaderOperator = GCodeLoaderOperatorModule.GCodeLoaderOperator


class G2G3ConfirmationDialog(bpy.types.Operator):
    bl_idname = "wm.g2g3confirmation"
    bl_label = "Confirm Arc Fitting"

    # This function will be executed when the user clicks 'OK'
    def execute(self, context):
        return {'FINISHED'}

    # This function shows the confirmation dialog
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, title="Confirm Arc Fitting", message="Your file contains G2/G3 GCode commands.\nWhile they are supported and should work, it is still a work in progress and possibly buggy. It is recommended to turn 'Arc Fitting' off in your slicer settings before generating the GCode.\nIt will make the addon and the renders slow, especially if you are using Bambu Studio.\nIf your loaded model appears broken in Blender this is possibly the culprit.\nIf you have already turned off Arc Fitting and still getting this warning, you can safely ignore it. Your slicer is just producing retraction commands that will be ignored by the addon", confirm_text="I understand, please proceed", icon="WARNING", translate=True)


class SlicerConfirmation(bpy.types.Operator):
    bl_idname = "wm.slicerconfirmation"
    bl_label = "Confirm Slicer Selection"

    message: bpy.props.StringProperty(
        name="Slicer_Message", default="No slicer was auto detected. Please manually select the slicer")

    # This function will be executed when the user clicks 'OK'
    def invoke(self, context, event):
        # Open the dialog with invoke_props_dialog
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        row = col.row()
        row.label(text=self.message)

        row = col.row()
        row.prop(context.scene.Stitcher_Props, "SlicerType")

    def execute(self, context):
        fileNameUpdationFunction(context.scene.Stitcher_Props, context)
        return {'FINISHED'}


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


class ShadowCatcherLoaderOperator(bpy.types.Operator):

    bl_idname = 'opr.shadow_catcher_loader'
    bl_label = 'Load Shadow Catcher'
    bl_description = "Load the shadow catcher. Only works with cycles"

    def execute(self, context):
        filepath = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.collections = [Keywords.shadowCatcherCollectionName]

        for col in data_to.collections:
            if col is not None:
                bpy.context.scene.collection.children.link(col)
        return {'FINISHED'}


class RenderSettingsOperator(bpy.types.Operator):

    bl_idname = 'opr.apply_render_settings'
    bl_label = 'Apply Recommended Render Settings'
    bl_description = "Applies the recommended settings for CYCLES render engine"
    bl_options = {'REGISTER', 'UNDO'}

    # This function will be executed when the user clicks 'OK'
    def execute(self, context):

        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.cycles.device = "GPU"

        # Access Cycles preferences
        cycles_prefs = bpy.context.preferences.addons['cycles'].preferences

        # Set the compute device type to CUDA (could also be 'OPTIX' or 'OPENCL')
        cycles_prefs.compute_device_type = 'CUDA'
        cycles_prefs.get_devices()
        # Enable all available CUDA devices (GPUs)
        for device in cycles_prefs.devices:
            if device.type == 'GPU':
                device.use = True

        bpy.context.scene.cycles.adaptive_threshold = 0.1
        bpy.context.scene.cycles.samples = 1024

        bpy.context.scene.cycles.max_bounces = 1
        bpy.context.scene.cycles.diffuse_bounces = 1
        bpy.context.scene.cycles.glossy_bounces = 1
        bpy.context.scene.cycles.transmission_bounces = 1
        bpy.context.scene.cycles.volume_bounces = 0
        bpy.context.scene.cycles.transparent_max_bounces = 1

        bpy.context.scene.cycles.caustics_reflective = False
        bpy.context.scene.cycles.caustics_refractive = False
        bpy.context.scene.cycles.volume_max_steps = 200
        bpy.context.scene.cycles.use_fast_gi = True

        bpy.context.scene.render.use_persistent_data = True
        bpy.context.scene.render.film_transparent = True

        bpy.context.scene.cycles.debug_use_compact_bvh = True
        return {'FINISHED'}

    # This function shows the confirmation dialog
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, title="Confirm Render Setting Application", message="These render settings are only for the CYCLES render engine. It will change your render engine to CYCLES.\nIf you are new, it is recommended to use EEVEE render engine and not use this option.", confirm_text="I understand, please proceed", icon="WARNING", translate=True)


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
        col.operator('opr.shadow_catcher_loader', text='Load Shadow Catcher')

        row = col.row()
        col.operator('opr.apply_render_settings', text='Apply Render Settings')

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
    print(self)
    context.scene.Stitcher_Props.Loading_Ready = False
    self.Status = "Preprocessing the File"
    startTime = time.time()

    filename, file_extension = os.path.splitext(self.FilePath)

    if file_extension == '.gcode':
        file = open(self.FilePath, 'r')
        print(self.FilePath)

        fi = io.FileIO(file.fileno())
        fb = io.BufferedReader(fi)

        slicerName = Keywords.Slicers.none
        selectedSlicerName = self.SlicerType
        line = fb.readline()

        while line:
            line = line.decode().strip()
            if bool(Patterns.PrusaSlicerPattern.search(line)):
                slicerName = Keywords.Slicers.prusa
                break

            elif bool(Patterns.OrcaSlicerPattern.search(line)):
                slicerName = Keywords.Slicers.orca
                break

            elif bool(Patterns.BambuStudioPattern.search(line)):
                slicerName = Keywords.Slicers.bambu
                break

            elif len(line) == 0:
                break

            line = fb.readline()

        if slicerName == Keywords.Slicers.none:
            slicerName = selectedSlicerName

        if slicerName != Keywords.Slicers.none:
            self.SlicerType = slicerName
            typesSet = set()
            filamentSet = set()
            line = fb.readline()

            typePattern = Patterns.printerSpecificPatterns[slicerName]['typePattern']
            filamentChangePattern = Patterns.printerSpecificPatterns[
                slicerName]['filamentChangePattern']
            curveGcodePattern = Patterns.curveGcodePattern
            g2g3Found = False

            while line:
                line = line.decode().strip()
                if patternMatcherFunction(typePattern, line):
                    curveType = patternMatcherSearch(
                        typePattern, line)[1].strip()
                    subbedType = re.sub(" |/", "_", curveType)
                    typesSet.add(subbedType)

                if patternMatcherFunction(filamentChangePattern, line):
                    filamentNumber = int(
                        patternMatcherSearch(filamentChangePattern, line)[1].strip())
                    filamentSet.add(filamentNumber)

                if patternMatcherFunction(curveGcodePattern, line):
                    g2g3Found = True

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

            context.scene.Stitcher_Props.Loading_Ready = True

            if g2g3Found:
                bpy.ops.wm.g2g3confirmation('INVOKE_DEFAULT')
                self.Status = "File contains G2/G3. Please Turn off Arc Fitting"

            else:
                self.Status = "File Preprocessing Done: took {}s".format(
                    timeTaken)
        else:
            bpy.ops.wm.slicerconfirmation('INVOKE_DEFAULT')
    else:
        showPopup(
            "Err 34: Please provide a valid GCode File with .gcode extension",
            "Invalid File", "ERROR")
        self.Status = "Invalid File"


class Stitcher_Props(bpy.types.PropertyGroup):

    ObjectName: bpy.props.StringProperty(
        name='Object Name', description='What to name the imported object collection', default='OBJECT')
    FilePath: bpy.props.StringProperty(
        name='File Path', description="Path of GCode file", subtype="FILE_PATH", update=fileNameUpdationFunction)
    SlicerType: bpy.props.EnumProperty(
        name="Slicer", description="Choose the slicer that was use to generate the GCode.", items=slicerItems)

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
    SlicesPerPrintLine: bpy.props.IntProperty(
        name='Slices Per Print Line', description="Number of slices for one print line", default=5, min=3, max=11)

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
    G2G3ConfirmationDialog, SlicerConfirmation, RenderSettingsOperator, KeyValueType, Stitcher_Props, Options, TypeFilters, GCodeLoaderOperator, Animatable, AssetLoaderOperator, ShadowCatcherLoaderOperator, NonAnimatable, ExternalPerimeterSelector, GeometryNodesApplicator,
]

propsMain = [
    'ObjectName',  'FilePath', 'SlicerType'
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
