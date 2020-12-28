import numpy as np
import plotly.graph_objects as go
from hotwing_core.utils import isect_line_plane_v3


class ParsedGcode:

    @classmethod
    def fromgcode(cls, gcode):
        def impute(f, H):
            if f is None and len(H)>0:
                f = H[-1]
            elif f is None:
                f = 0.0
            return f

        commands = gcode._commands
        X, Y, U, V, TAG, KIND = [],[],[],[],[],[]
        for c in commands:
            if c.type_ in ["MOVE","FAST_MOVE"]:
                X.append(impute(c.data.get('x',None), X))
                Y.append(impute(c.data.get('y',None), Y))
                U.append(impute(c.data.get('u',None), U))
                V.append(impute(c.data.get('v',None), V))
                TAG.append(c._options)
                KIND.append(c.type_)
                    
        return cls(X,Y,U,V,TAG, KIND)

        
    def __init__(self, X,Y,U,V,TAG, KIND):
        self.X = X
        self.Y = Y
        self.U = U
        self.V = V
        self.TAG = TAG
        self.KIND = KIND

    def zip(self):
        return zip(self.X, self.Y, self.U, self.V, self.TAG, self.KIND)

    def __len__(self):
        return len(self.X)


    def filter_gcode(self, options_to_include = ["initial_move","profile","done_profile", "front_stock", "tail_stock"], kind_to_include=["MOVE","FAST_MOVE"]):
        X_f, Y_f, U_f, V_f, TAG_f, KIND_f = [],[],[],[],[], []

        for x,y,u,v,t,k in self.zip():
            int_tag = set(t).intersection(options_to_include)
            if len(int_tag) > 0 and k in kind_to_include:
                X_f.append(x)
                Y_f.append(y)
                U_f.append(u)
                V_f.append(v)
                TAG_f.append(int_tag.pop())
                KIND_f.append(k)

        return ParsedGcode(X_f, Y_f, U_f, V_f, TAG_f, KIND_f)


class GcodeBox():
    def __init__(self, box_left, box_width, box_bottom, box_height, box_inset, box_depth):
        self.left = box_left
        self.width = box_width
        self.bottom = box_bottom
        self.height = box_height
        self.inset = box_inset
        self.depth = box_depth

class GcodePlotter():
    def __init__(self, machine_width, machine_height, machine_depth, foam_left_offset, foam_width, foam_bottom_offset, foam_height, foam_depth_offset, foam_depth):
        # box representing the bounds of the machine
        self.mbox = GcodeBox(0, machine_width, 0, machine_height, 0, machine_depth)
        # box representing the bounds of the foam block
        self.fbox = GcodeBox(foam_left_offset, foam_width, foam_bottom_offset, foam_height, foam_depth_offset, foam_depth)

    
    def setup_fig(self, fig):
        ''' returns a figure plotly object, with some defaults on aspect ratio, margins and so on''' 
    
        fig.update_layout(scene_aspectmode='data')
        fig.update_layout(
            scene = dict(
                xaxis = dict(nticks=4,showbackground=False),
                yaxis = dict(nticks=1,showbackground=False),
                zaxis = dict(nticks=1,showbackground=False),),
            margin=dict(r=20, l=10, b=10, t=10))
        return fig


    def project_coords(self, pgc: ParsedGcode, from_box: GcodeBox, to_box: GcodeBox):
        ''' Projects the gcode coordinates in X, Y, U & V onto the foam block start (left_offset) and foamblock end (left_offset+panelwidth)
            Used to visualize the wing no the foam block'''

        def project_line(x,y,u,v, width, offset):
            ''' Projects a line between two 3d coordinates onto a surface at "offset" and returns the 3d coordinates of the point where it intersects'''
            c1_3d = (0, x, y)
            c2_3d = (width, u, v)  
            p_no = (1, 0, 0)
            position = [offset,0,0]
            a = isect_line_plane_v3(c1_3d, c2_3d, position, p_no)
            return a

        n = len(pgc)
        X1, Y1, U1, V1 = [], [], [], []

        for i in range(n):
            a = project_line(pgc.X[i], pgc.Y[i], pgc.U[i], pgc.V[i], from_box.width, to_box.left)
            X1.append(a[1])
            Y1.append(a[2])
            
            b = project_line(pgc.X[i], pgc.Y[i], pgc.U[i], pgc.V[i], from_box.width, to_box.left + to_box.width)
            U1.append(b[1])
            V1.append(b[2])
            
        return ParsedGcode(X1, Y1, U1, V1, pgc.TAG, pgc.KIND)


    def calc_vertices(self, pgc: ParsedGcode, gbox: GcodeBox, points):
        '''build triangles for the wing surface visualization
        X, Y, U, V is the gcode coordinates
        the output x,y,z,i,j,k is in the format needed by plotly Mesh3d'''
        x = np.zeros(points) 
        x = np.append(x, np.ones(points) * gbox.width)
        x = x + gbox.left

        y = np.array(pgc.X[:points], np.float64)
        y = np.append(y, np.array(pgc.U[:points]))

        z = np.array(pgc.Y[:points], np.float64)
        z = np.append(z,np.array(pgc.V[:points], np.float64))
        
        i = []
        j = []
        k = []
        for a in range(points-1):
            #first triangle
            i.append(a)
            j.append(a+points)
            k.append(a+1)
            
            #second triangle
            i.append(a+points)
            j.append(a+points+1)
            k.append(a+1) 

        intensity = (x< gbox.left) | (x> gbox.left + gbox.width) \
                    | (y< gbox.inset) | (y>gbox.depth + gbox.inset) \
                    | (z< gbox.bottom) | (z > gbox.height + gbox.bottom)
        intensity = np.array(intensity,float) 
            
        return {'x':x, 'y':y, 'z':z, 'i':i, 'j':j, 'k':k, 'intensity':intensity}


    def make_foam_block(self):
        x = np.array([0,0,1,1,0,0,1,1], np.float) * (self.fbox.width) + self.fbox.left
        y = np.array([0,1,1,0,0,1,1,0],np.float) * self.fbox.depth + self.fbox.inset

        z = np.array([0,0,0,0,1,1,1,1], np.float) * self.fbox.height + self.fbox.bottom
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]

        return {'x':x, 'y':y, 'z':z, 'i':i, 'j':j, 'k':k}


    def plot_gcode(self, pgcode : ParsedGcode, num_of_points=-1, draw_cutting_path = True, draw_foam_block=True):
        '''returns a plotly figure object visualizing the cut path (optional) and the wing foam paths'''

        pgcode_wing = self.project_coords(pgcode, self.mbox, self.fbox)

        if num_of_points == -1:
            num_of_points = len(pgcode_wing)

        wing_vertices = self.calc_vertices(pgcode_wing, self.fbox, num_of_points )

        fig = go.Figure(data=[
            go.Mesh3d(
                **wing_vertices,
                showscale=False,
                colorscale=[[0, 'green'], [1, 'red']],
                cmin = 0, cmax=1
            )
        ])
        fig = self.setup_fig(fig)

        if draw_cutting_path:
            pillar_vertices = self.calc_vertices(pgcode, self.mbox, num_of_points )
            fig.add_trace(
                go.Mesh3d(
                    **pillar_vertices, 
                    opacity=0.50, 
                    showscale=False, 
                    cmin=0, cmax=1,
                    colorscale=[[0, 'gold'],[1, 'red']],)
                )
            
        if draw_foam_block:
            foam_vertices = self.make_foam_block()
            fig.add_trace(
                go.Mesh3d(
                    **foam_vertices, 
                    color='gray', 
                    opacity=0.50)
                )
            
        
        #fig.update_scenes(xaxis_autorange="reversed")
        return fig
