import unicodedata
import string
import dash_html_components as html
from hotwing_core.utils import isect_line_plane_v3
from operator import itemgetter
import math
import numpy as np


validFilenameChars = "-_.()%s%s" % (string.ascii_letters, string.digits)

def removeDisallowedFilenameChars(filename):
    cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode()
    clist = []
    for c in cleanedFilename:
        if not c in validFilenameChars:
            c = "_"
        clist.append(c)
    return ''.join(clist)

def list_to_html(input_list):
    result = html.Ul(
        [html.Li(s) for s in input_list]
    )
    return result


def argmin(a):
    return min(enumerate(a), key=itemgetter(1))[0]

def argmax(a):
    return max(enumerate(a), key=itemgetter(1))[0]


def project_line(x,y,u,v, width, offset):
    ''' Projects a line between two 3d coordinates onto a surface at "offset" and returns the 3d coordinates of the point where it intersects'''
    c1_3d = (0, x, y)
    c2_3d = (width, u, v)  
    p_no = (1, 0, 0)
    position = [offset,0,0]
    a = isect_line_plane_v3(c1_3d, c2_3d, position, p_no)
    return a

def rotate(p, origin=(0, 0), degrees=0):
    angle = np.deg2rad(degrees)
    R = np.array([[np.cos(angle), -np.sin(angle)],
                  [np.sin(angle),  np.cos(angle)]])
    o = np.atleast_2d(origin)
    p = np.atleast_2d(p)
    return np.squeeze((R @ (p.T-o.T) + o.T).T)


def prep_file_for_saving(input_str):
    lines = input_str.split("\n")
    result = "\n;".join(lines)
    return ";" + result


def parse_uploaded(input_str):
    lines = input_str.split("\n")
    return "\n".join([l[1:] for l in lines if l.startswith(";") and not l.startswith(";Generated")])


def get_temp_filename(folder):
    import tempfile
    with tempfile.NamedTemporaryFile(dir=folder, delete=False) as tmpfile:
        temp_file_name = tmpfile.name
    return temp_file_name