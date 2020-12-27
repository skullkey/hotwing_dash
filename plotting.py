import numpy as np
import plotly.graph_objects as go
from hotwing_core.utils import isect_line_plane_v3

def parse_gcode(code):
    def check_all_filled(parts):
        result = True
        for p in parts[:-1]:
            if p.strip()=="":
                result = False
                break
        return result

    X = []
    Y = []
    U = []
    V = []
    for line in code:
        if line.startswith('MOVE'):
            parts = line.split("\t")
            if check_all_filled(parts):
                parts = [float(p) for p in parts[1:-1]]
                X.append(parts[0])
                Y.append(parts[1])
                U.append(parts[2])
                V.append(parts[3])
                
    return X,Y,U,V


def calc_vertices(X,Y,U,V, left_offset, width, height,depth, points):
    '''build triangles for the wing surface visualization
    X, Y, U, V is the gcode coordinates
    the output x,y,z,i,j,k is in the format needed by plotly Mesh3d'''
    x = np.zeros(points) 
    x = np.append(x, np.ones(points) * width)
    x = x + left_offset

    y = np.array(X[:points], np.float64)
    y = np.append(y, np.array(U[:points]))

    z = np.array(Y[:points], np.float64)
    z = np.append(z,np.array(V[:points], np.float64))
    
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

    intensity = (x< left_offset) | (x> left_offset + width) | (y<0) | (y>depth) | (z<0) | (z > height)
    intensity = np.array(intensity,float) 
        
    return x,y,z,i,j,k, intensity

def make_vertices_fig(fig):
    ''' returns a figure plotly object, with some defaults on aspect ratio, margins and so on''' 
    
    fig.update_layout(scene_aspectmode='data')
    fig.update_layout(
        scene = dict(
            xaxis = dict(nticks=4,showbackground=False),
            yaxis = dict(nticks=1,showbackground=False),
            zaxis = dict(nticks=1,showbackground=False),),
        margin=dict(r=20, l=10, b=10, t=10))
    return fig


def project_line(x,y,u,v, machine_width, offset):
    ''' Projects a line between two 3d coordinates onto a surface at "offset" and returns the 3d coordinates of the point where it intersects'''
    c1_3d = (0, x, y)
    c2_3d = (machine_width, u, v)  
    p_no = (1, 0, 0)
    position = [offset,0,0]
    a = isect_line_plane_v3(c1_3d, c2_3d, position, p_no)
    return a

def project_coords(X,Y,U,V,width, left_offset, panel_width):
    ''' Projects the gcode coordinates in X, Y, U & V onto the foam block start (left_offset) and foamblock end (left_offset+panelwidth)
        Used to visualize the wing no the foam block'''
    n = len(X)
    X1 = []
    Y1 = []
    U1 = []
    V1 = []

    for i in range(n):
        a = project_line(X[i],Y[i],U[i],V[i], width, left_offset)
        X1.append(a[1])
        Y1.append(a[2])
        
        b = project_line(X[i],Y[i],U[i],V[i], width, left_offset+panel_width)
        U1.append(b[1])
        V1.append(b[2])
        
    return X1, Y1, U1, V1

def make_foam_block(left_offset, panel_width, panel_height, panel_depth):
    x = np.array([0,0,1,1,0,0,1,1], np.float) * (panel_width) + left_offset 
    y = np.array([0,1,1,0,0,1,1,0],np.float) * panel_depth

    z = np.array([0,0,0,0,1,1,1,1], np.float) * panel_height
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]

    return x,y,z,i,j,k


def plot_gcode(gcode, machine_width, machine_height, machine_depth, left_offset, panel_width, panel_height, panel_depth, num_of_points=-1, draw_cutting_path = True, draw_foam_block=True):
    '''returns a plotly figure object visualizing the cut path (optional) and the wing foam paths'''
    X, Y, U, V = parse_gcode(gcode)
    X1, Y1, U1, V1 = project_coords(X, 
                                    Y, 
                                    U, 
                                    V, 
                                    width = machine_width, 
                                    left_offset = left_offset,  
                                    panel_width = panel_width)

    if num_of_points == -1:
        num_of_points = len(X)
    wing_x,wing_y, wing_z, wing_i, wing_j, wing_k, color_intensity =calc_vertices(X1,Y1,U1,V1, left_offset, panel_width, panel_height, panel_depth, num_of_points )

    fig = go.Figure(data=[
        go.Mesh3d(
            x=wing_x,
            y=wing_y,
            z=wing_z,

            i = wing_i,
            j = wing_j,
            k = wing_k,
            showscale=False,
            colorscale=[[0, 'green'],
                    [1, 'red']],
            cmin = 0, cmax=1,
            intensity=color_intensity
        )
    ])
    fig = make_vertices_fig(fig)

    if draw_cutting_path:
        pillar_x,pillar_y,pillar_z,pillar_i,pillar_j,pillar_k, pillar_intensity =calc_vertices(X,Y,U,V,0, machine_width,machine_height, machine_depth, num_of_points )
        fig.add_trace(go.Mesh3d(x=pillar_x, y=pillar_y, z=pillar_z, i=pillar_i, j=pillar_j, k=pillar_k, 
            intensity=pillar_intensity, opacity=0.50, showscale=False, cmin=0, cmax=1,colorscale=[[0, 'gold'],[1, 'red']],))
        
    if draw_foam_block:
        x,y,z,i,j,k = make_foam_block(left_offset, panel_width, panel_height, panel_depth)
        fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=i, j=j, k=k, color='gray', opacity=0.50))
        
    
    #fig.update_scenes(xaxis_autorange="reversed")
    return fig
