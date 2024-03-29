import ezdxf
import svgpathtools



import math
import re
import os
import numpy as np
import utils
from collections import OrderedDict
from simplification.cutil import simplify_coords_vw_idx


def rotate(p, origin=(0, 0), degrees=0):
    angle = np.deg2rad(degrees)
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle),  np.cos(angle)]])
    o = np.atleast_2d(origin)
    p = np.atleast_2d(p)
    return np.squeeze((R @ (p.T-o.T) + o.T).T)



class GCodeObj:
    def __init__(self):
        pass

class Line(GCodeObj):
    def __init__(self, start,end):
        self.start = start
        self.end = end
        
    def to_gcode(self, coord_list):
        coord_list.append(self.start)
        coord_list.append(self.end)
        
    def first_point(self):
        return self.start
    
    def last_point(self):
        return self.end
    
    def reverse(self):
        d = self.end
        self.end = self.start
        self.start = d
        
        
class LWPolyLine(GCodeObj):
    def __init__(self, points):
        self.points = points
        
        
    def to_gcode(self, coord_list):
        for p in self.points:
            coord_list.append(p)
            
            
    def first_point(self):
        return self.points[0]
    
    def last_point(self):
        return self.points[-1]
    
    
    def reverse(self):
        self.points.reverse()
            
    



class DxfToGCode:
    TOL = 1e-9
    def __init__(self, doc):
        self.doc = doc
        self.gco_list = []
        self.gco_parsed_list = []
        self._parse()
        
        
    def _parse(self):

        self.gco_list = []

        # iterate over all entities in modelspace
        msp = self.doc.modelspace()
        for e in msp:
            if(e.dxftype() == "LINE"):
                start = tuple(e.dxf.start)[:2]
                end = tuple(e.dxf.end)[:2]
                self.gco_list.append(Line(start,end)) 
            elif e.dxftype() == "LWPOLYLINE":
                with e.points('xy') as points:
                    newpoints = [p for p in points]
                self.gco_list.append(LWPolyLine(newpoints))
            else:
                raise Exception("Unsupported DXF Type:",e.dxftype())

        self.gco_parsed_list = self.gco_list.copy()

    def _reset_gco_list(self):
        self.gco_list = self.gco_parsed_list.copy()

    def find_first_xy(self):
        self._reset_gco_list()
        obj = self.gco_list[0]
        while obj is not None:
            last_point = obj.last_point()
            obj = self.find_next(obj.last_point())
        
        
        return last_point 
                
    def find_next(self, coord):
        def dist(t1,t2):
            return math.sqrt((t1[0]-t2[0])**2 + (t1[1] - t2[1]) **2)
        
        for i,obj in enumerate(self.gco_list):
            if dist(obj.first_point(), coord) < self.TOL:
                del self.gco_list[i]
                return obj
            if dist(obj.last_point(), coord)  < self.TOL:
                del self.gco_list[i]
                obj.reverse()
                return obj
        return None
    
    
    def to_gcode(self,x_offset, y_offset, rotate_angle, scale_factor, four_axis, feedrate = 160, pwm = 100):
        gcode_list = [f"; x_offset = {x_offset}", f"; y_offset = {y_offset}", f"; rotate_angle = {rotate_angle}", f" scale_factor = {scale_factor}"]
        gcode_list.extend(["G21","G90","G1 F%.3f" % feedrate, "M3 S%d" % pwm ])
        
        x_series, y_series, _, _, _, _ = self.to_xy_array(x_offset, y_offset, rotate_angle, scale_factor)
        coord_list = zip(x_series, y_series)
        
        if four_axis:
            gcode_list.extend(["G1 X%.4f Y%.4f Z%.4f A%.4f" % (x,y,x,y) for x,y in coord_list])  
        else:
            gcode_list.extend(["G1 X%.4f Y%.4f" % (x,y) for x,y in coord_list])
            
        gcode_list.append("M5")
        return gcode_list 

    def to_xy_array(self, x_offset, y_offset, rotate_angle, scale_factor, ignore_offset=False, add_zero=True):
        start_x,start_y =  self.find_first_xy()

        self._reset_gco_list()
        obj =  self.find_next((start_x,start_y))
                
        coord_list = []
        while obj is not None:
            obj.to_gcode(coord_list)
            obj = self.find_next(obj.last_point())  

        if not ignore_offset:
            coord_list = [(x * scale_factor,y * scale_factor) for x,y in coord_list  ]
            coord_list = rotate(coord_list, degrees = rotate_angle)
        else:
            scale_factor = 1.
            rotate_angle = 0.

        min_x = min([x for x,y in coord_list])
        min_y = min([y for x,y in coord_list])


        if ignore_offset:
            x_offset = min_x  
            y_offset = min_y 

        x_series = [x+x_offset-min_x for x,y in coord_list]
        x_series.append(x_series[0])
        if add_zero:
            x_series.insert(0,0)
            x_series.append(0)

        y_series  = [y+y_offset-min_y for x, y in coord_list]
        y_series.append(y_series[0])
        if add_zero:
            y_series.insert(0,0)
            y_series.append(0)

        return x_series, y_series, x_offset, y_offset, rotate_angle, scale_factor

    def to_selig(self, profilename, x_offset, y_offset, rotate_angle, scale_factor):
        x_series, y_series, _,_,_,_ = self.to_xy_array(x_offset,y_offset, rotate_angle, scale_factor, False, False)
        
        # simplify
        points = [(x,y) for x,y in zip(x_series,y_series)]
        idx = simplify_coords_vw_idx(points, 0.1)

        x_series = [points[x][0] for x in idx]
        y_series = [points[y][1] for y in idx]

        # roll coordinates 
        items_to_shift = np.argmin(x_series)

        x_series = np.roll(x_series, -items_to_shift)
        y_series = np.roll(y_series, -items_to_shift)


        org_x = x_series[0]
        org_y = y_series[0]
        x_series = np.array([x-org_x for x in x_series], dtype=np.double)
        y_series = np.array([y-org_y for y in y_series], dtype=np.double)


        max_index = np.argmax(x_series)
        max_x = np.max(x_series)

        first, second = np.mean(y_series[:max_index]), np.mean(y_series[max_index:])

        if first < second:
            x_series = np.flipud(x_series)
            y_series = np.flipud(y_series)
            items_to_shift = np.argmin(x_series)
            x_series = np.roll(x_series, -items_to_shift)
            y_series = np.roll(y_series, -items_to_shift)


        print(x_series, y_series)
        max_index = np.argmax(x_series)


        #make sure x is unique
        x_series_top = [round(x,3)+i/1000 for i,x in enumerate(x_series[:max_index+1])]
        max_x_top = max(x_series_top)
        min_x_top = min(x_series_top)
        x_series_top = [( x -  min_x_top)/(max_x_top - min_x_top) for x in x_series_top[:-1]]
        

        x_series_bot = [round(x,3)-i/1000 for i,x in enumerate(x_series[max_index:])]
        max_x_bot = max(x_series_bot)
        min_x_bot = min(x_series_bot)
        x_series_bot = [(x - min_x_bot)/(max_x_bot - min_x_bot) for x in x_series_bot]

        #print(x_series_top, x_series_bot)

        x_series = x_series_top
        x_series.extend(x_series_bot)


        profile = [((1. - x),y/(max_x)) for x,y in zip(x_series,y_series)]        

        # doing some gymnastics here because the selig format does not allow duplicate x-coordinates 

        #runs = utils.runs(x_series)

        #profile_top =    OrderedDict( (round(xy[0],3)-i/100000. ,  (round(xy[0],3) - i/100000.,round(xy[1],3))) for i,xy in zip(runs[:max_index],profile[:max_index])).values()
        #profile_bottom = OrderedDict( (round(xy[0],3)+i/100000. ,  (round(xy[0],3) + i/100000.,round(xy[1],3))) for i,xy in zip(runs[max_index:],profile[max_index:])).values()
        #profile_top.extend(profile_bottom)
        #if profile[-1] != (1.,0.):
        #    profile_top.append(profile_top[0])

        profile_top = [(x,round(y,3)) for (x,y) in profile[:max_index]]
        profile_bottom = [(x, round(y,3)) for (x,y) in profile[max_index:]]
        profile_top.extend(profile_bottom)
        #if profile_top[-1] != (1.,0.):
        #    profile_top.append(profile_top[0])



        output = [profilename]
        for x,y in profile_top:
            output.append("    %.5f     %.3f" % (x,y))

        return output



class GcodeToGcode(DxfToGCode):
    def __init__(self, gcode_lines):
        self.gcode_lines = gcode_lines
        DxfToGCode.__init__(self, None)
        


    def _parse(self):
        self.gco_list = []

        xy_coord = re.compile(r"[xX]([-]?[0-9\.]*) [yY]([-]?[0-9\.]*)")
        
        newpoints = []
        for line in self.gcode_lines:
            if line.startswith('G1'):
                xy = xy_coord.search(line)
                if xy is not None:
                    x = float(xy.group(1))
                    y = float(xy.group(2))
                    newpoints.append((x,y))

        del newpoints[0]
        del newpoints[-1]
        self.gco_list.append(LWPolyLine(newpoints))

        self.gco_parsed_list = self.gco_list.copy()



class SVGToGcode(DxfToGCode):
    def __init__(self, paths):
        self.paths = paths
        DxfToGCode.__init__(self, None)

    def _parse(self):
        self.gco_list = []

    
        for path in self.paths:
            newpoints = []
            for segment in path:
                for i in np.arange(0,1,0.05):
                    c = segment.point(i)
                    x,y = c.real,c.imag
                    newpoints.append((x,y))
            self.gco_list.append(LWPolyLine(newpoints))
        

        self.gco_parsed_list = self.gco_list.copy()



def create_parser(stored_filename):
        _,extension =  os.path.splitext(stored_filename)
        extension = extension.lower()

        if extension == '.dxf':
            doc = ezdxf.readfile(stored_filename)
            dxfp = DxfToGCode(doc)

        elif extension == '.svg':
            paths,_ = svgpathtools.svg2paths(stored_filename)
            dxfp = SVGToGcode(paths)
        elif extension == '.gcode':
            with open(stored_filename) as f:
                lines = f.readlines()
            dxfp = GcodeToGcode(lines)
        else:
            raise Exception("Unsupported filetype")

        return dxfp


def paths_to_str(paths, bboxes):
    min_x, min_y,max_x, max_y = bboxes[0]
    for i,bbox in enumerate(bboxes):
        if i>0:
            min_x = min(min_x, bbox[0])
            min_y = min(min_y, bbox[1])
            max_x = max(max_x, bbox[2])
            max_y = max(max_y, bbox[3])
            

    doc = svgpathtools.wsvg(paths,paths2Drawing=True, dimensions=("%smm" % max_x,"%smm" % max_y),  stroke_widths=[1]*10)
    return doc.tostring()

def series_to_path(data, max_y):
    x_series = data['x']
    y_series = data['y']
    y_series = [max_y - y for y in y_series]

    min_x = min(x_series)
    min_y = min(y_series)
    max_x = max(x_series)
    max_y = max(y_series)

    segs = []
    for i,(x,y) in enumerate(zip(x_series,y_series)):
        if i >0:
            seg = svgpathtools.Line(prev_x+prev_y*1j,x+y*1j)
            segs.append(seg)
        prev_x = x
        prev_y = y
     
    return svgpathtools.Path(*segs), (min_x, min_y, max_x, max_y)


def simplify_profile(data):

    left = data['left']
    right = data['right']

    x_series = left['x']
    left_dist = max(x_series) - min(x_series)
    y_series = left['y']
    left_points = [[x,y] for x,y in zip(x_series,y_series)]

    x_series = right['x']
    y_series = right['y']
    right_dist = max(x_series) - min(x_series)
    right_points = [[x,y] for x,y in zip(x_series,y_series)]

    if left_dist > right_dist:
        idxs = simplify_coords_vw_idx(left_points, 0.1)

    else:
        idxs = simplify_coords_vw_idx(right_points, 0.1)



    new_left_points = [left_points[i] for i in idxs]
    new_left_points.append(left_points[0]) # close the profile

    new_right_points = [right_points[i] for i in idxs]
    new_right_points.append(right_points[0]) # close the profile


    #
    output = {'left':{},'right':{}}
    output['left']['x'] = [a[0] for a in new_left_points]
    output['left']['y'] = [a[1] for a in new_left_points]
    output['right']['x'] = [a[0] for a in new_right_points]
    output['right']['y'] = [a[1] for a in new_right_points]

    return output
