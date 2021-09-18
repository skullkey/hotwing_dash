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


def paths_to_str(paths):
    doc = svgpathtools.wsvg(paths,paths2Drawing=True)
    return doc.tostring()

def series_to_path(data):
    x_series = data['x']
    y_series = data['y']
    segs = []
    for i,(x,y) in enumerate(zip(x_series,y_series)):
        if i >0:
            seg = svgpathtools.Line(prev_x-prev_y*1j,x-y*1j)
            segs.append(seg)
        prev_x = x
        prev_y = y
     
    return svgpathtools.Path(*segs)