from pickle import TRUE
from pydoc import describe
from random import seed
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

modulesNames = [ 'Constants','ExtruderErrorCreator', 'Exceptions', 'EndPointCreator', 'BevelShapeCreator', 'GCodeReader', 'Meshifier' ]

modulesFullNames = {}
for currentModuleName in modulesNames:
    modulesFullNames[currentModuleName] = ('{}.{}'.format(__name__, currentModuleName))
 
for currentModuleFullName in modulesFullNames.values():
    import importlib
    if currentModuleFullName in sys.modules:
        importlib.reload(sys.modules[currentModuleFullName])
    else:
        globals()[currentModuleFullName] = importlib.import_module(currentModuleFullName)
        setattr(globals()[currentModuleFullName], 'modulesNames', modulesFullNames)

ParamNames = sys.modules[modulesFullNames['Constants']].ParamNames
Keywords = sys.modules[modulesFullNames['Constants']].Keywords
GCodeReader = sys.modules[modulesFullNames['GCodeReader']]
class GCodeLoaderOperator(bpy.types.Operator):
    
    bl_idname = 'opr.gcode_loader'
    bl_label = 'Load GCode'
    bl_description = "Load the GCode and construct the model"

    """def execute(self, context):

        fileName = getattr(bpy.context.scene.Stitcher_Props, 'FilePath')
        
        params = {}
        for propGroup in propsNonAnimatable:
            
            if (isinstance(propGroup, str)):
                params[propGroup] = getattr(bpy.context.scene.Stitcher_Props, propGroup)
            elif(isinstance(propGroup, tuple)):
                params[propGroup[0]] = {}
                for prop in propGroup[1:]:
                    params[propGroup[0]][prop[1]] = getattr(bpy.context.scene.Stitcher_Props, prop[0])
                    
        params[ParamNames.seed] = 237

        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.materials = [Keywords.materialName]
            data_to.node_groups = [Keywords.geoNodesName]
        
        sys.modules[modulesFullNames['GCodeReader']].builder(fileName, params=params)
        return {'FINISHED'}"""

    def modal(self, context, event):
        if self.state == 2:
            print("")
            self.endTime = time.time()

            timeTaken = self.endTime - self.startTime

            bpy.context.scene["Stitcher_Object_Collection"] = self.parentCollection
            bpy.context.scene.Stitcher_Props.Status = "Processing Done took {}s".format(timeTaken)
            return {'FINISHED'}
        elif self.state == 0:
            self.coin = sys.modules[modulesFullNames['Constants']].BiasedCoin(self.params[ParamNames.seed])

            self.objectName = getattr(bpy.context.scene.Stitcher_Props, 'ObjectName')
            self.bevelSuffix = getattr(bpy.context.scene.Stitcher_Props, 'BevelName')

            i = 0
            
            self.parentCollection =  bpy.data.collections.new(self.objectName)
            bpy.context.scene.collection.children.link(self.parentCollection)

            self.numberOfLayers = len(self.listOfParsedLayers) - 1
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
            coords = []

            
            layerCollection = bpy.data.collections.new("Layer " + str(currentLayer.layerNumber))
            self.parentCollection.children.link(layerCollection)

            def placeCurveFunc(curveType):
            
                curveOB = GCodeReader.placeCurve(coords, prevWidth, prevHeight, currentLayer.zPos, prevType, currentLayer.layerNumber, self.bevelSuffix, layerCollection, self.params)
                if (not curveOB == None):
                    GCodeReader.addVisibilityDriver(curveOB, "hide_viewport")
                    GCodeReader.addVisibilityDriver(curveOB, "hide_render")
                

                if (curveType in ["External_perimeter", "Skirt_Brim", "Perimeter", "Top_solid_infill", "Overhang_perimeter"] and not curveOB == None ):
                    endPoint, startPoint = sys.modules[modulesFullNames['GCodeReader']].createEndPoints(curveOB, self.params, self.coin)
                    layerCollection.objects.link(endPoint)
                    layerCollection.objects.link(startPoint)
                    
                    GCodeReader.addVisibilityDriver(endPoint, "hide_viewport")
                    GCodeReader.addVisibilityDriver(startPoint, "hide_viewport")
                    GCodeReader.addVisibilityDriver(endPoint, "hide_render")
                    GCodeReader.addVisibilityDriver(startPoint, "hide_render")
                    curveOB[Keywords.startPoint] = startPoint
                    curveOB[Keywords.endPoint] = startPoint

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
            print("Layer Done: {}/{}".format(currentLayer.layerNumber, self.numberOfLayers), end='\r', flush=True)

            bpy.context.scene.Stitcher_Props.Status = "Layer Done: {}/{}".format(currentLayer.layerNumber, self.numberOfLayers)
            
            self.report({'INFO'}, "Layer Done: {}/{}".format(currentLayer.layerNumber, self.numberOfLayers))
            
            return {'RUNNING_MODAL'}





    def invoke(self, context, event):
        self.startTime = time.time()
        fileName = getattr(bpy.context.scene.Stitcher_Props, 'FilePath')
        
        params = {}
        for propGroup in propsNonAnimatable:
            
            if (isinstance(propGroup, str)):
                params[propGroup] = getattr(bpy.context.scene.Stitcher_Props, propGroup)
            elif(isinstance(propGroup, tuple)):
                params[propGroup[0]] = {}
                for prop in propGroup[1:]:
                    params[propGroup[0]][prop[1]] = getattr(bpy.context.scene.Stitcher_Props, prop[0])
                    
        params[ParamNames.seed] = 237
        params[ParamNames.whPrecision] = 2

        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.materials = [Keywords.materialName]
            data_to.node_groups = [Keywords.geoNodesName]

        self.fileName = fileName
        self.params = params
        self.state = 0
        self.i = 0
        self.listOfParsedLayers = GCodeReader.gcodeParser(self.fileName, self.params)

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class AssetLoaderOperator(bpy.types.Operator):
    
    bl_idname = 'opr.asset_loader'
    bl_label = 'Load Assets'
    bl_description = "Load the plate, backdrop and camera and lighting"

    def execute(self, context):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.collections = [Keywords.importCollectionName]
            
        
        for col in data_to.collections:
            if col is not None:
                bpy.context.scene.collection.children.link(col)
        return {'FINISHED'}

class MeshifyOperator(bpy.types.Operator):
    bl_idname = 'opr.meshifier'
    bl_label = 'Meshify!!!'
    bl_description = "VERY SLOW, VERY EXPERIMENTAL!!! DO NOT USE!!!\nConverts everything to mesh"

    def execute(self, context):
        sys.modules[modulesFullNames['Meshifier']].meshify(bpy.context.scene["Stitcher_Object_Collection"])
        return {'FINISHED'}

class ExternalPerimeterSelector(bpy.types.Operator):
    
    bl_idname = 'opr.external_perimeter_selector'
    bl_label = 'Load Assets'
    
    def execute(self, context):
        seed = 237
        probability = getattr(bpy.context.scene.Stitcher_Props, 'ExtruderError_Probability')

        sys.modules[modulesFullNames['ExtruderErrorCreator']].makeSelection(bpy.context.scene["Stitcher_Object_Collection"], probability, seed)
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
    

class Options(PanelParent ):
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





class Filters(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_options"
    bl_idname = 'VIEW3D_PT_panel_fiters'
    bl_label = "Filters"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column()
        row = col.row()
        row.prop(context.scene.Stitcher_Props,'ViewportOnly')
        row = col.row()
        row.label(text="Features:")
        for propName in propsFilter:
            row = col.row()
            row.prop(context.scene.Stitcher_Props, propName)
        
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

    #('Extruder Error',('ExtruderError_Density', 'Density'),('ExtruderError_Probability', 'Probability'))
    def draw(self, context):
        col = self.layout.column()
        for propGroup in propsNonAnimatable:
            
            if (isinstance(propGroup, str)):
                row = col.row()
                row.prop(context.scene.Stitcher_Props, propGroup)
            elif(isinstance(propGroup, tuple)):
                row = col.row()
                row.label(text=propGroup[0]+":")
                row = col.row()
                for prop in propGroup[1:]:
                    row.prop(context.scene.Stitcher_Props, prop[0], text=prop[1])

        row = col.row()
        row.label(text="Extruder Error")
        row = col.row()
        row.prop(context.scene.Stitcher_Props, 'ExtruderError_Probability', text='Probability')
        row.operator('opr.external_perimeter_selector', text='Make Selection')
        
        row = col.row()
        row.prop(context.scene.Stitcher_Props, 'ExtruderError_Density', text='Density')
        row.operator('opr.geometry_nodes_applicator', text='Apply Errors')
        row.enabled = bool(len(context.selected_objects))



class Stitcher_Props(bpy.types.PropertyGroup):
    ObjectName: bpy.props.StringProperty(name='Object Name', description='What to name the imported object collection', default='OBJECT')
    BevelName: bpy.props.StringProperty(name='Bevel Name', description='What to name the created bevel profiles', default='bevel')
    FilePath: bpy.props.StringProperty(name='File Path', description="Path of GCode file", subtype="FILE_PATH")
    
    SeamAbberation_Amount: bpy.props.FloatProperty(name='Seam Abberation Distance', default=0, description='The maximum amount to vary the seams', min=0)
    SeamAbberation_Probability: bpy.props.FloatProperty(name='Seam Abberation Probability', default=0, description='The probability with which a seam would be picked to be varied.\n0 being none and 1 being all', min=0, max=100)
    
    WidthOffset: bpy.props.FloatProperty(name='Width Offset', default=0, description='All the lines widths would be offset by this amount', min=-1, max=1)
    HeightOffset: bpy.props.FloatProperty(name='Height Offset', default=0, description='All the lines heights would be offset by this amount ', min=-1, max=1)
    Precision: bpy.props.IntProperty(name='Precision', description="What decimal place to round off the GCode Coordinates to", default=4, min=2, max=10)
    ExtruderError_Density: bpy.props.FloatProperty(name='Extruder Error Density', default=0.1, description='The density of extruder mistakes', min=0.00, max=1.00, step=0.05)
    ExtruderError_Probability: bpy.props.FloatProperty(name='Extruder Error Probability', default=0, description='The probability with which a point would be picked to be varied.\n0 being none and 1 being all', min=0)

    Gap_fill: bpy.props.BoolProperty(name='Gap fill', default=True)
    External_perimeter: bpy.props.BoolProperty(name='External perimeter', default=True)
    Overhang_perimeter: bpy.props.BoolProperty(name='Overhang perimeter', default=True)
    Perimeter: bpy.props.BoolProperty(name='Perimeter', default=True)
    Top_solid_infill: bpy.props.BoolProperty(name='Top solid infill', default=True)
    Bridge_infill: bpy.props.BoolProperty(name='Bridge infill', default=True)
    Internal_infill: bpy.props.BoolProperty(name='Internal infill', default=True)
    Custom: bpy.props.BoolProperty(name='Custom', default=True)
    Solid_infill: bpy.props.BoolProperty(name='Solid infill', default=True)
    Skirt_Brim: bpy.props.BoolProperty(name='Skirt/Brim', default=True)
    Support_material: bpy.props.BoolProperty(name='Support material', default=True)
    Support_material_interface: bpy.props.BoolProperty(name='Support material interface', default=True)
    
    ViewportOnly: bpy.props.BoolProperty(name='Viewport Only', description="The filters below would only affect the viewport.\nThe features would still appear in the render", default=True)

    End_Point: bpy.props.BoolProperty(name='End Point', default=True)
    Extruder_Error: bpy.props.BoolProperty(name='Extruder Error', default=True)


    SeamDistance: bpy.props.FloatProperty(name='Seam Distance', default=0.2, description='How far apart should the seams be to get a desired look', min=0)
    LayerIndexTop: bpy.props.IntProperty(name='Layer Index', default=5000, description='The topmost layer to show, every layer after this would be hidden', min=0)

    Status: bpy.props.StringProperty(name='Status', description='Processing Status', default='Not Processing')

CLASSES = [
    Stitcher_Props, Options, Filters, GCodeLoaderOperator, Animatable, AssetLoaderOperator, NonAnimatable, ExternalPerimeterSelector, GeometryNodesApplicator, MeshifyOperator
]

propsMain = [
    'ObjectName', 'BevelName', 'FilePath'
    ]

propsFilter = ['Gap_fill', 'External_perimeter', 'Perimeter', 'Top_solid_infill', 'Bridge_infill', 'Internal_infill', 'Custom', 'Solid_infill', 'Skirt_Brim', 'End_Point', 'Overhang_perimeter', 'Support_material', 'Support_material_interface', 'Extruder_Error']
propsAnimatable = ['SeamDistance', 'LayerIndexTop']
propsNonAnimatable = ['WidthOffset', 'HeightOffset', 'Precision', ('Seam Abberations', ('SeamAbberation_Amount', 'Amount'), ('SeamAbberation_Probability', 'Probability')), ] 


def register():
    print('registered') # just for debug
    for klass in CLASSES:
        bpy.utils.register_class(klass)

    bpy.types.Scene.Stitcher_Props = bpy.props.PointerProperty(type=Stitcher_Props)

    

def unregister():
    print('unregistered') # just for debug
    for klass in CLASSES:
        bpy.utils.unregister_class(klass)


    del bpy.types.Scene.Stitcher_Props

    

if __name__ == '__main__':
    register()