import numpy as np
import plotly.graph_objects as go


from utils import argmax,argmin, project_line


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

    def _round(self, a):
        return np.round(np.array(a, 'float32'),2)

    @property
    def round_X(self):
        return self._round(self.X)

    @property
    def round_Y(self):
        return self._round(self.Y)

    @property
    def round_U(self):
        return self._round(self.U)

    @property
    def round_V(self):
        return self._round(self.V)

class GcodeBox():
    def __init__(self, box_left, box_width, box_bottom, box_height, box_inset, box_depth):
        self.left = box_left
        self.width = box_width
        self.bottom = box_bottom
        self.height = box_height
        self.inset = box_inset
        self.depth = box_depth

class GcodePlotter():
    def __init__(self, machine_width, machine_height, machine_depth, 
                      foam_left_offset, foam_width, foam_bottom_offset, foam_height, foam_depth_offset, foam_depth,
                      wing_plan, bbox):
        # box representing the bounds of the machine
        self.mbox = GcodeBox(0, machine_width, 0, machine_height, 0, machine_depth)
        # box representing the bounds of the foam block
        self.fbox = GcodeBox(foam_left_offset, foam_width, foam_bottom_offset, foam_height, foam_depth_offset, foam_depth)
        # coordinates of the wing in plan [left_top, right_top, right_bottom, left_bottom]
        self.wing_plan = wing_plan
        # boudning box [bottom_left, top_right]
        self.bbox = bbox

    
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
            
        return {'x':np.round(x,2), 'y':np.round(y,2), 'z':np.round(z,2) , 'i':i, 'j':j, 'k':k, 'intensity':intensity}


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

        stats = {}
        pgcode_wing = self.project_coords(pgcode, self.mbox, self.fbox)

        if num_of_points == -1:
            num_of_points = len(pgcode_wing)

        wing_vertices = self.calc_vertices(pgcode_wing, self.fbox, num_of_points )
        stats['wing'] = self.summarize_vertices(wing_vertices)

        fig = go.Figure() 
        fig = self.setup_fig(fig)


        

        if draw_cutting_path:
            pillar_vertices = self.calc_vertices(pgcode, self.mbox, num_of_points )
            stats['machine'] = self.summarize_vertices(pillar_vertices)
            fig.add_trace(
                go.Mesh3d(
                    **pillar_vertices, 
                    opacity=0.50, 
                    showscale=False, 
                    cmin=0, cmax=1,
                    colorscale=[[0, 'gold'],[1, 'red']],
                    showlegend= True, name='Cut')
                )
            
        if draw_foam_block:
            foam_vertices = self.make_foam_block()
            stats['block'] = self.summarize_vertices(foam_vertices)

            fig.add_trace(
                go.Mesh3d(
                    **foam_vertices, 
                    color='gray', 
                    opacity=0.50, showlegend=True, name='Foam')
                )
            
        
        fig.add_trace(
            go.Mesh3d(
                **wing_vertices,
                showscale=False,
                colorscale=[[0, 'green'], [1, 'red']],
                cmin = 0, cmax=1, showlegend=True, name='Wing'
            )
        )

        
        #fig.update_scenes(xaxis_autorange="reversed")
        return fig, stats


    def plot_gcode_2dprofile(self, pgcode : ParsedGcode, num_of_points=-1, 
                draw_cutting_path = True, draw_foam_block=True, draw_machine_block = True):
        '''returns a plotly figure object visualizing the cut path (optional) and the wing foam paths'''

        stats = {}
        pgcode_wing = self.project_coords(pgcode, self.mbox, self.fbox)


        fig = go.Figure() 
        fig = self.setup_fig(fig)

        if draw_cutting_path:
            
            fig.add_trace(
                go.Scatter(
                    x = pgcode.round_X, 
                    y = pgcode.round_Y,
                    opacity=0.50, name="Cut Left", visible='legendonly',
                    line={"color":"yellow"}
                    )
                )
            fig.add_trace(
                go.Scatter(
                    x = pgcode.round_U, 
                    y = pgcode.round_V,
                    opacity=0.50, name="Cut Right", visible='legendonly',
                    line={"color":"gold"}
                    )
                )

        if draw_foam_block:
            x0=self.fbox.inset
            y0=self.fbox.bottom
            x1=self.fbox.inset + self.fbox.depth
            y1=self.fbox.bottom + self.fbox.height
            fig.add_trace(
                go.Scatter(
                    x = [x0,x1,x1,x0,x0], 
                    y = [y0,y0,y1,y1,y0],
                    name = "Foam",
                    line={"color":"gray"}
                )
            )
            

        # draw machine extents   
        if draw_machine_block:
            
            x0=self.mbox.inset
            y0=self.mbox.bottom
            x1=self.mbox.inset + self.mbox.depth
            y1=self.mbox.bottom + self.mbox.height
            fig.add_trace(
                go.Scatter(
                    x = [x0,x1,x1,x0], 
                    y = [y0,y0,y1,y1],
                    name = "Machine"
                )
            )

        # draw the wing profile
        fig.add_trace(
                go.Scatter(
                    x = pgcode_wing.round_X, 
                    y = pgcode_wing.round_Y,
                    opacity=0.50, name="Wing Left",
                    line={"color":"olive"}
                    )
                )
        fig.add_trace(
            go.Scatter(
                x = pgcode_wing.round_U, 
                y = pgcode_wing.round_V,
                opacity=0.50, name="Wing Right",
                line={"color":"green"}
                )
            )

        stats['left'] = {"x":pgcode_wing.X, "y":pgcode_wing.Y}
        stats['right'] = {"x":pgcode_wing.U, "y":pgcode_wing.V}
        
        #fig.update_scenes(xaxis_autorange="reversed")
        return fig, stats


    def plot_gcode_2dplan(self, pgcode : ParsedGcode, num_of_points=-1, 
                draw_cutting_path = True, draw_foam_block=True, draw_machine_block = True):
        '''returns a plotly figure object visualizing the cut path (optional) and the wing foam paths'''



        stats = {}
        pgcode_wing = self.project_coords(pgcode, self.mbox, self.fbox)


        fig = go.Figure() 
        fig = self.setup_fig(fig)

        if draw_cutting_path:

            i = argmin(pgcode.X)
            min_line = (pgcode.round_X[i], pgcode.round_U[i])
            i = argmax(pgcode.X)
            max_line = (pgcode.round_X[i], pgcode.round_U[i])

             
            x0=float(self.mbox.left)
            y0=float(min_line[0])

            x1=self.mbox.left + self.mbox.width
            y1=min_line[1]

            x2=self.mbox.left + self.mbox.width
            y2=max_line[1]

            x3=self.mbox.left 
            y3=max_line[0]



            fig.add_trace(
                go.Scatter(
                    x = [x0,x1,x2,x3,x0], 
                    y = [y0,y1,y2,y3,y0],
                    name = "Cut Path",
                    line={"color":"gold"}
                )
            )

        if draw_foam_block:
            x0=self.fbox.left
            y0=self.fbox.inset
            x1=self.fbox.left + self.fbox.width
            y1=self.fbox.inset + self.fbox.depth
            fig.add_trace(
                go.Scatter(
                    x = [x0,x1,x1,x0,x0], 
                    y = [y0,y0,y1,y1,y0],
                    name = "Foam",
                    line={"color":"gray"}
                )
            )
            

        # draw machine extents   
        if draw_machine_block:
            
            x0=self.mbox.left   
            y0=self.mbox.inset
            x1=self.mbox.left + self.mbox.width
            y1=self.mbox.inset + self.mbox.depth
            fig.add_trace(
                go.Scatter(
                    x = [x0,x1,x1,x0,x0], 
                    y = [y0,y0,y1,y1,y0],
                    name = "Machine",
                    line={"color":"black"}
                    
                )
            )

        # draw the wing profile

        # left from projection
        x0 = float(self.fbox.left)
        delta_x = 0 


        # top from projection
        y_top = float(max(pgcode_wing.round_X))

        # top  from wingplan
        bl = self.wing_plan[0]
        delta_y = bl[1] - y_top

        # overlay the wing plan on the projected location
        wing_x = []
        wing_y = []
        for c in self.wing_plan:
            wing_x.append(c[0] - delta_x)
            wing_y.append(c[1] - delta_y)

        wing_x.append(self.wing_plan[0][0] - delta_x)
        wing_y.append(self.wing_plan[0][1] - delta_y)

        stats['x'] = wing_x
        stats['y'] = wing_y

        x_coords = []
        y_coords = []

        for i,(x,y) in enumerate(zip(wing_x,wing_y)):
            if i ==0:
                prev_x = x

                prev_y = y
            else:
                steps = int(max(abs(x - prev_x) + 1,abs(y - prev_y) + 1))
                x_coords.extend(np.linspace(prev_x,x,steps))
                y_coords.extend(np.linspace(prev_y,y, steps))

                prev_x = x
                prev_y = y


        fig.add_trace(
                go.Scatter(
                    x = x_coords, 
                    y = y_coords,
                    name = "Wing Plan",
                    line = {"color":"green"}
                )
            )

        
        #fig.update_scenes(xaxis_autorange="reversed")
        return fig, stats

    def summarize_vertices(self, vertices):
        result = {}
        for ax in ('x','y','z'):
            result[f'min_{ax}'] = np.min(vertices[ax])
            result[f'max_{ax}'] = np.max(vertices[ax])
            result[f'dist_{ax}'] = result[f'max_{ax}'] -  result[f'min_{ax}'] 

        if 'intensity' in vertices:
            result['out_of_bounds'] = np.sum(vertices['intensity'])
        else:
            result['out_of_bounds'] = None

        return result


