from pickle import TRUE
import bpy

bl_info = {
    # required
    'name': 'My Example Addon',
    'blender': (2, 93, 0),
    'category': 'Object',
    'location': "View3D > Tools > MyPlugin",
    # optional
    'version': (1, 0, 0),
    'author': 'Mina Pêcheux',
    'description': 'An example addon',
}

class PanelParent(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "3D-Print Buddy"
    bl_options = {"DEFAULT_CLOSED"}

class Options(PanelParent ):
    bl_idname = 'VIEW3D_PT_panel_1'
    bl_label = 'Options'

    def draw(self, context):
        col = self.layout.column()
        for (prop_name, _) in propsMain:
            row = col.row()
            row.prop(context.scene, prop_name)

class Filters(PanelParent):
    bl_parent_id = "VIEW3D_PT_panel_1"
    bl_label = "Filters"

    def draw(self, context):
        col = self.layout.column()
        for (prop_name, _) in propsFilter:
            row = col.row()
            row.prop(context.scene, prop_name)
        

CLASSES = [
    Options, Filters
]

propsMain = [
    ('Object Name', bpy.props.StringProperty(name='Object Name', description='What to name the imported object collection', default='OBJECT')),
    ('Bevel Name', bpy.props.StringProperty(name='Bevel Name', description='What to name the created bevel profiles', default='bevel')),
]

propsFilter = list(map( lambda x: (x, bpy.props.BoolProperty(name=x, default=True)) ,['Gap fill', 'External perimeter', 'Perimeter', 'Top solid infill', 'Bridge infill', 'Internal infill', 'Custom', 'Solid infill', 'Skirt/Brim']))

def register():
    print('registered') # just for debug
    for klass in CLASSES:
        bpy.utils.register_class(klass)

    for (prop_name, prop_value) in propsMain:
        setattr(bpy.types.Scene, prop_name, prop_value)

    for (prop_name, prop_value) in propsFilter:
        setattr(bpy.types.Scene, prop_name, prop_value)

def unregister():
    print('unregistered') # just for debug
    for klass in CLASSES:
        bpy.utils.unregister_class(klass)

    for (prop_name, _) in propsMain:
        delattr(bpy.types.Scene, prop_name)
    
    for (prop_name, _) in propsFilter:
        delattr(bpy.types.Scene, prop_name)


if __name__ == '__main__':
    register()