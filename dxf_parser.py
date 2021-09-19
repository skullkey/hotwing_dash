import ezdxf
import svgpathtools



import math
import re
import os
import numpy as np
import utils
from collections import OrderedDict



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
    
    
    def to_gcode(self,x_offset, y_offset, four_axis, feedrate = 160, pwm = 100):
        gcode_list = [f"; x_offset = {x_offset}", f"; y_offset = {y_offset}"]
        gcode_list.extend(["G21","G90","G1 F%.3f" % feedrate, "M3 S%d" % pwm ])
        
        x_series, y_series, _, _ = self.to_xy_array(x_offset, y_offset)
        coord_list = zip(x_series, y_series)
        
        if four_axis:
            gcode_list.extend(["G1 X%.4f Y%.4f Z%.4f A%.4f" % (x,y,x,y) for x,y in coord_list])  
        else:
            gcode_list.extend(["G1 X%.4f Y%.4f" % (x,y) for x,y in coord_list])
            
        gcode_list.append("M5")
        return gcode_list 

    def to_xy_array(self, x_offset, y_offset, ignore_offset=False, add_zero=True):
        start_x,start_y =  self.find_first_xy()

        self._reset_gco_list()
        obj =  self.find_next((start_x,start_y))
                
        coord_list = []
        while obj is not None:
            obj.to_gcode(coord_list)
            obj = self.find_next(obj.last_point())  

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

        return x_series, y_series, x_offset, y_offset

    def to_selig(self, profilename):
        x_series, y_series, _,_ = self.to_xy_array(0,0,False, False)



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

        print(max_x, x_series[:3])
        profile = [((max_x - x)/(max_x),y/(max_x)) for x,y in zip(x_series,y_series)]        

        max_index = np.argmax(x_series)

        # doing some gymnastics here because the selig format does not allow duplicate x-coordinates 

        runs = utils.runs(x_series)

        profile_top =    list(OrderedDict( (round(xy[0],3)-i/100000. ,  (round(xy[0],3) - i/100000.,round(xy[1],3))) for i,xy in zip(runs[:max_index],profile[:max_index])).values())
        profile_bottom = list(OrderedDict( (round(xy[0],3)+i/100000. ,  (round(xy[0],3) + i/100000.,round(xy[1],3))) for i,xy in zip(runs[max_index:],profile[max_index:])).values())
        profile_top.extend(profile_bottom)
        if profile[-1] != (1.,0.):
            profile_top.append(profile_top[0])

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

def series_to_path(data):
    x_series = data['x']
    y_series = data['y']
    max_y = max(y_series)
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
    left_points = [(x,y) for x,y in zip(x_series,y_series)]

    x_series = right['x']
    y_series = right['y']
    right_dist = max(x_series) - min(x_series)
    right_points = [(x,y) for x,y in zip(x_series,y_series)]

    if left_dist > right_dist:
        new_left_points, idxs = visvalingham_whyatt(left_points, min_points = 50, inplace=False)
        new_left_points.append(left_points[0]) # close the profile
        new_right_points = [right_points[i] for i in idxs]
        new_right_points.append(right_points[0]) # close the profile

    else:
        new_right_points, idxs = visvalingham_whyatt(right_points, min_points = 50, inplace=False)
        new_right_points.append(right_points[0]) # close the profile
        new_left_points = [left_points[i] for i in idxs]
        new_left_points.append(left_points[0]) # close the profile

    print(new_left_points)
    print(new_right_points)


    #
    output = {'left':{},'right':{}}
    output['left']['x'] = [a[0] for a in new_left_points]
    output['left']['y'] = [a[1] for a in new_left_points]
    output['right']['x'] = [a[0] for a in new_right_points]
    output['right']['y'] = [a[1] for a in new_right_points]

    return output


# from https://dougfenstermacher.com/blog/simplification-summarization
import math


def triangle_area(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ab = a - b
    ab_dist = np.linalg.norm(ab)

    cb = c - b
    cb_dist = np.linalg.norm(cb)
    fraction = np.dot(ab, cb) / (ab_dist * cb_dist)
    if fraction > 1. :
        fraction = 1.
    elif fraction < -1.:
        fraction = -1.
    theta = math.acos(fraction)
    return 0.5 * ab_dist * cb_dist * math.sin(theta)


def visvalingham_whyatt(points, **kwargs):
    """
    Visvalingham-Whyatt algorithm for polyline simplification

    Runs in  linear O(n) time

    Parameters:
        points(list): list of sequential points in the polyline

    Keyword Arguments:
        min_points(int):  Minimum number of points in polyline, defaults to 2
        inplace (bool):  Indicates if the input polyline should remove points from the input list, defaults to False

    Returns:
        list: A list of min_points of the simplified polyline
    """
    point_count = len(points)
    if not kwargs.get('inplace', False):
        new_points = list(points)
    else:
        new_points = points
    areas = [float('inf')]
    point_indexes = list(range(point_count -1))
    for i in range(1, point_count - 1):
        area = triangle_area(points[i - 1], points[i], points[i + 1])
        areas.append(area)

    min_points = kwargs.get('min_points', 2)
    while len(new_points) > min_points:
        smallest_effective_index = min(point_indexes, key=lambda i: areas[i])
        new_points.pop(smallest_effective_index)
        areas.pop(smallest_effective_index)
        point_count = len(new_points)
        point_indexes = list(range(point_count -1))
        # recompute area for point after previous_smallest_effective_index
        if smallest_effective_index > 1:
            areas[smallest_effective_index - 1] = triangle_area(new_points[smallest_effective_index - 2], new_points[smallest_effective_index - 1], new_points[smallest_effective_index])
        # recompute area for point before previous smallest_effective_index
        if smallest_effective_index < point_count - 1:
            areas[smallest_effective_index] = triangle_area(new_points[smallest_effective_index - 1], new_points[smallest_effective_index], new_points[smallest_effective_index + 1])
    return new_points, point_indexes



def perpendicular_distance(point, a, b):
    """
    perpendicular distance between a point and a line segment

    Arguments:
        point (tuple|list): The point
        a (tuple|list): The start point of the line segment
        b (tuple|list): The end point of the line segment

    Returns:
        float: perpendicular distance
    """
    point = np.array(point)
    a = np.array(a)
    b = np.array(b)
    ba = b - a
    numerator = np.linalg.norm(np.cross(ba, b-point))
    denominator = np.linalg.norm(ba)
    return numerator/denominator


def ramer_douglas_peucker(points, epsilon):
    """
    Algorithm that decimates a curve composed of line segments to a similar curve with fewer points

    Arguments:
        points(list): list of sequential points in the polyline
        epsilon (int|float): The maximum distance from the existing line to be considered an essential point

    Returns:
        list:  The simplified polyline
    """
    dmax = 0
    index = 0

    for i in range(1, len(points) - 1):
        d = perpendicular_distance(points[i], points[0], points[-1])
        if d > dmax:
            index = i
            dmax = d

    if dmax > epsilon:
        results1 = ramer_douglas_peucker(points[:index + 1], epsilon)[:-1]
        results2 = ramer_douglas_peucker(points[index:], epsilon)
        results = results1 + results2
    else:
        results = [points[0], points[-1]]
    return results
