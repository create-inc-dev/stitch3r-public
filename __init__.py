from pickle import TRUE
from random import seed
import bpy
import sys
import os

bl_info = {
    'name': 'My Example Addon',
    'blender': (2, 93, 0),
    'category': 'Object',
    'location': "View3D > Tools > MyPlugin",
    'version': (1, 0, 0),
    'author': 'Vipul Rajan',
    'description': 'An example addon',
}

modulesNames = [ 'Constants', 'ExtruderErrorCreator', 'Exceptions', 'EndPointCreator', 'BevelShapeCreator', 'GCodeReader' ]

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
class GCodeLoaderOperator(bpy.types.Operator):
    
    bl_idname = 'opr.gcode_loader'
    bl_label = 'Load GCode'
    
    def execute(self, context):

        fileName = getattr(bpy.context.scene.Buddy_Props, 'FilePath')
        
        params = {}
        for propGroup in propsNonAnimatable:
            
            if (isinstance(propGroup, str)):
                params[propGroup] = getattr(bpy.context.scene.Buddy_Props, propGroup)
            elif(isinstance(propGroup, tuple)):
                params[propGroup[0]] = {}
                for prop in propGroup[1:]:
                    params[propGroup[0]][prop[1]] = getattr(bpy.context.scene.Buddy_Props, prop[0])
                    
        params[ParamNames.seed] = 237
        params[ParamNames.precision] = 2

        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets.blend")
        with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
            data_to.materials = [Keywords.materialName]
            data_to.node_groups = [Keywords.geoNodesName]
        
        sys.modules[modulesFullNames['GCodeReader']].builder(fileName, params=params)
        return {'FINISHED'}

class AssetLoaderOperator(bpy.types.Operator):
    
    bl_idname = 'opr.asset_loader'
    bl_label = 'Load Assets'
    
    def execute(self, context):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets.blend")
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
        probability = getattr(bpy.context.scene.Buddy_Props, 'ExtruderError_Probability')

        sys.modules[modulesFullNames['ExtruderErrorCreator']].makeSelection(bpy.context.scene["Buddy_Object_Collection"], probability, seed)
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
    bl_category = "3D-Print Buddy"
    

class Options(PanelParent ):
    bl_idname = 'VIEW3D_PT_panel_options'
    bl_label = 'Options'
    
    def draw(self, context):
        col = self.layout.column()
        for propName in propsMain:
            row = col.row()
            row.prop(context.scene.Buddy_Props, propName)

        row = col.row()
        col.operator('opr.gcode_loader', text='Load GCode')
        row = col.row()
        col.operator('opr.asset_loader', text='Load Assets')





class Filters(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_options"
    bl_idname = 'VIEW3D_PT_panel_fiters'
    bl_label = "Filters"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column()
        row = col.row()
        row.prop(context.scene.Buddy_Props,'ViewportOnly')
        row = col.row()
        row.label(text="Features:")
        for propName in propsFilter:
            row = col.row()
            row.prop(context.scene.Buddy_Props, propName)
        
class Animatable(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_options"
    bl_idname = 'VIEW3D_PT_panel_animatable'
    bl_label = "Animatable"

    def draw(self, context):
        col = self.layout.column()
        for propName in propsAnimatable:
            row = col.row()
            row.prop(context.scene.Buddy_Props, propName)

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
                row.prop(context.scene.Buddy_Props, propGroup)
            elif(isinstance(propGroup, tuple)):
                row = col.row()
                row.label(text=propGroup[0]+":")
                row = col.row()
                for prop in propGroup[1:]:
                    row.prop(context.scene.Buddy_Props, prop[0], text=prop[1])

        row = col.row()
        row.label(text="Extruder Error")
        row = col.row()
        row.prop(context.scene.Buddy_Props, 'ExtruderError_Probability', text='Probability')
        row.operator('opr.external_perimeter_selector', text='Make Selection')
        
        row = col.row()
        row.prop(context.scene.Buddy_Props, 'ExtruderError_Density', text='Density')
        row.operator('opr.geometry_nodes_applicator', text='Apply Errors')
        row.enabled = bool(len(context.selected_objects))



class Buddy_Props(bpy.types.PropertyGroup):
    ObjectName: bpy.props.StringProperty(name='Object Name', description='What to name the imported object collection', default='OBJECT')
    BevelName: bpy.props.StringProperty(name='Bevel Name', description='What to name the created bevel profiles', default='bevel')
    FilePath: bpy.props.StringProperty(name='File Path', description="Path of GCode file", subtype="FILE_PATH")
    
    SeamAbberation_Amount: bpy.props.FloatProperty(name='Seam Abberation Distance', default=0, description='The maximum amount to vary the seams', min=0)
    SeamAbberation_Probability: bpy.props.FloatProperty(name='Seam Abberation Probability', default=0, description='The probability with which a seam would be picked to be varied.\n0 being none and 1 being all', min=0, max=100)
    WidthOffset: bpy.props.FloatProperty(name='Width Offset', default=0, description='All the lines widths would be offset by this amount', min=-1, max=1)
    HeightOffset: bpy.props.FloatProperty(name='Height Offset', default=0, description='All the lines heights would be offset by this amount ', min=-1, max=1)
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
    
    ViewportOnly: bpy.props.BoolProperty(name='Veiwport Only', description="The filters below would only affect the viewport.\nThe features would still appear in the render", default=True)

    End_Point: bpy.props.BoolProperty(name='End Point', default=True)
    Extruder_Error: bpy.props.BoolProperty(name='Extruder Error', default=True)


    SeamDistance: bpy.props.FloatProperty(name='Seam Distance', default=0.2, description='How far apart should the seams be to get a desired look', min=0)
    LayerIndexTop: bpy.props.IntProperty(name='Layer Index', default=5000, description='The topmost layer to show, every layer after this would be hidden', min=0)

    Status = bpy.props.StringProperty(name='Status', description="Processing Status", default="Not Processing")

CLASSES = [
    Buddy_Props, Options, Filters, GCodeLoaderOperator, Animatable, AssetLoaderOperator, NonAnimatable, ExternalPerimeterSelector, GeometryNodesApplicator
]

propsMain = [
    'ObjectName', 'BevelName', 'FilePath'
    ]

propsFilter = ['Gap_fill', 'External_perimeter', 'Perimeter', 'Top_solid_infill', 'Bridge_infill', 'Internal_infill', 'Custom', 'Solid_infill', 'Skirt_Brim', 'End_Point', 'Overhang_perimeter', 'Support_material', 'Support_material_interface', 'Extruder_Error']
propsAnimatable = ['SeamDistance', 'LayerIndexTop']
propsNonAnimatable = ['WidthOffset', 'HeightOffset', ('Seam Abberations', ('SeamAbberation_Amount', 'Amount'), ('SeamAbberation_Probability', 'Probability')), ] 


def register():
    print('registered') # just for debug
    for klass in CLASSES:
        bpy.utils.register_class(klass)

    bpy.types.Scene.Buddy_Props = bpy.props.PointerProperty(type=Buddy_Props)

    

def unregister():
    print('unregistered') # just for debug
    for klass in CLASSES:
        bpy.utils.unregister_class(klass)


    del bpy.types.Scene.Buddy_Props

    

if __name__ == '__main__':
    register()