import bpy
from mathutils import Vector
from bpy import context 
import re

from numpy import poly 


def createProfile(width, height):
    curveData = bpy.data.curves.new('bevelObject', type='CURVE')
    curveData.dimensions = '3D'

    
    point1 = [(-1*(width - height)/2, 0, 0), (-1*((width - height)/2 + height),0,0), (-1*((width - height)/2 - height),0,0)]
    point2 = [((width - height)/2, 0, 0), ((width - height)/2 - height,0,0), ((width - height)/2 + height,0,0)]
    point3 = [((width - height)/2, -1*height, 0), ((width - height)/2 + height, -1*height, 0), ((width - height)/2 - height, -1*height, 0)]
    point4 = [(-1*(width - height)/2, -1*height, 0), (-1*(width - height)/2 + height, -1*height, 0), (-1*(width - height)/2 - height, -1*height, 0)]

    coords = [point1, point2, point3, point4]

    polyline = curveData.splines.new('BEZIER')
    polyline.bezier_points.add(len(coords)-1)
    polyline.use_endpoint_u= True;
    polyline.use_cyclic_u = True;


    for i, coord in enumerate(coords):
        polyline.bezier_points[i].co = coord[0]
        polyline.bezier_points[i].handle_left_type = 'FREE'
        polyline.bezier_points[i].handle_left = coord[1]
        polyline.bezier_points[i].handle_right_type = 'FREE'
        polyline.bezier_points[i].handle_right = coord[2]

    # create Object
    curveOB = bpy.data.objects.new('bevelObject', curveData)

    # attach to scene and validate context
    view_layer = bpy.context.view_layer
    curveOB = bpy.data.objects.new('bevelObject', curveData)
    view_layer.active_layer_collection.collection.objects.link(curveOB)

createProfile(0.35,0.2)


    


