import ezdxf
import math
import re
import os


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

    def to_xy_array(self, x_offset, y_offset, ignore_offset=False):
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
        x_series.insert(0,0)
        x_series.append(0)

        y_series  = [y+y_offset-min_y for x, y in coord_list]
        y_series.append(y_series[0])
        y_series.insert(0,0)
        y_series.append(0)

        return x_series, y_series, x_offset, y_offset


class GcodeToGcode(DxfToGCode):
    def __init__(self, gcode_lines):
        self.gcode_lines = gcode_lines
        DxfToGCode.__init__(self, None)
        


    def _parse(self):
        self.gco_list = []

        xy_coord = re.compile(r"[xX]([0-9\.]*) [yY]([0-9\.]*)")
        
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


def create_parser(stored_filename):
        _,extension =  os.path.splitext(stored_filename)
        extension = extension.lower()

        if extension == '.dxf':
            doc = ezdxf.readfile(stored_filename)
            dxfp = DxfToGCode(doc)
        elif extension == '.gcode':
            with open(stored_filename) as f:
                lines = f.readlines()
            dxfp = GcodeToGcode(lines)

        return dxfp
