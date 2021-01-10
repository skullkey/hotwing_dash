from __future__ import division
from hotwing_core.profile import Profile
from hotwing_core.rib import Rib
from hotwing_core.machine import Machine
from hotwing_core.panel import Panel
from hotwing_core.coordinate import Coordinate
from hotwing_core.gcode import Gcode
import datetime
from importlib import reload

import trailing_cutting_strategy
import config_options
import gcode_formatter
import os

import ssl
import urllib.request
import json

# Most of this code borrowed from hotwing-cli

def validate_kerf(kerf):
    # should receive a string
    if "," in kerf:
        k = kerf.split(',')
        return (float(k[0]),float(k[1]))
    else:
        return float(kerf)


class ProfileCache():
    def __init__(self, path):
        self.cache = {}

        if not os.path.isdir(path):
            os.mkdir(path)

        self.path = path

        self.load()

    def load(self):
        try:
            with open(self.path + "/cache.json") as f:
                self.cache = json.load(f)
        except:
            self.cache = {}

    def save(self):
        with open(self.path + "/cache.json", "w") as f:
            json.dump(self.cache, f)

    def is_url(self, url):
        if url.strip().lower().startswith("http"):
            return True
        else:
            return False

    def get_profile_filename(self, url):
        if self.is_url(url):

            filename = self.cache.get(url, None)
            if filename is None:
                gcontext = ssl.SSLContext()
                try:
                    req = urllib.request.Request(url)
                    res = urllib.request.urlopen(req, context=gcontext)
                    contents = res.read().decode('utf-8')
                except Exception as e:
                    raise Exception(f"Could not open url:{url}")

                lines = contents.split("\n")
                profile_name = lines[0].strip()

                filename = f"{self.path}/{profile_name}.dat"
                with open(filename,"w") as f:
                    f.write(contents)

                self.cache[url] = filename
                self.save()

            return filename

        else:
            # not a url, so assume it is a filename
            return url

            



class GcodeGen():

    def __init__(self, config, profile_cache : ProfileCache):
        self.config = config
        self.points = self.config.get_config('Gcode','InterpolationPoints')
        self.pcache = profile_cache

    def gen_gcode(self):
        get_config = self.config.get_config
        root_offset =  get_config('Panel','RootChordOffset')
        side = get_config('Panel','TipChordSide')

        root_profile_filename = self.pcache.get_profile_filename(get_config('RootChord',"Profile"))


        rib1 = Rib( root_profile_filename, 
                            scale=get_config('RootChord',"Width"), 
                            xy_offset=Coordinate(get_config('RootChord',"LeadingEdgeOffset"),0), 
                            top_sheet=get_config('Wing',"SheetingTop"), 
                            bottom_sheet=get_config('Wing',"SheetingBottom"), 
                            front_stock=get_config('Wing',"StockLeadingEdge"), 
                            tail_stock=get_config('Wing',"StockTrailingEdge"),
                            rotation=get_config('RootChord',"Rotation"),
                            rotation_pos=get_config('RootChord',"RotationPosition"),
                            )

        tip_profile_filename = self.pcache.get_profile_filename(get_config('TipChord',"Profile"))

        rib2 = Rib( tip_profile_filename, 
                            scale=get_config('TipChord',"Width"), 
                            xy_offset=Coordinate(get_config('TipChord',"LeadingEdgeOffset"),0), 
                            top_sheet=get_config('Wing',"SheetingTop"), 
                            bottom_sheet=get_config('Wing',"SheetingBottom"), 
                            front_stock=get_config('Wing',"StockLeadingEdge"), 
                            tail_stock=get_config('Wing',"StockTrailingEdge"),
                            rotation=get_config('TipChord',"Rotation"),
                            rotation_pos=get_config('TipChord',"RotationPosition"),
                            )

        panel = Panel(rib1, rib2, get_config('Panel',"Width"))
        if side == "right":
            panel = Panel.reverse(panel)
            self.left_offset = root_offset
        else:
            self.left_offset = get_config('Machine',"Width") -  get_config('Panel',"Width") - root_offset

        if panel.width > get_config('Machine',"Width"):
                raise Exception("Error: Panel (%s) is bigger than the machine width (%s)." % (get_config('Machine',"Width"), panel.width) )

        machine = Machine(  width = get_config('Machine',"Width"), 
                        kerf =  validate_kerf(get_config('Machine',"Kerf")),
                        profile_points = self.points,
                        units = get_config('Project',"Units"),
                        feedrate = get_config('Machine',"Feedrate")
                    )

        machine.load_panel(left_offset= self.left_offset, panel=panel)

        safe_height = get_config('Panel',"SafeHeight")
        safe_height = safe_height if safe_height else get_config('Panel',"Height")*2
        machine.safe_height = safe_height
        machine.foam_height = get_config('Panel',"Height")

        machine.gc = Gcode(formatter_name=machine.gcode_formatter_name, 
                units=machine.units, 
                feedrate=machine.feedrate )

        prepend_list = []
        if get_config("Gcode","ConfigAsComment"):
            prepend_list.append("Generated: %s" % datetime.datetime.now().isoformat())
            config_str = self.config.config_as_str()
            prepend_list.extend(config_str.split("\n"))
            prepend = "\n;".join(prepend_list)
            prepend = ";" + prepend
        else:
            prepend = None

       

        machine.gc.gcode_formatter = gcode_formatter.CustomGcodeFormatter(machine.gc,
                             get_config("Gcode","AxisMapping"),
                             get_config("Gcode","GcodeWireOn"),
                             get_config("Gcode","GcodeWireOff"),
                             prepend)

        cs = trailing_cutting_strategy.TrailingEdgeCuttingStrategy(machine)

        if side == "right":
            vertical_offset_left = get_config("Wing","VerticalOffsetRoot")
            vertical_offset_right = get_config("Wing","VerticalOffsetTip")
        else:
            vertical_offset_left = get_config("Wing","VerticalOffsetTip")
            vertical_offset_right = get_config("Wing","VerticalOffsetRoot")

        vertical_align_profiles = get_config("Wing","VerticalAlignProfiles")
        dihedral = get_config("Wing","Dihedral")


        cs.cut(get_config("Wing","HorizontalOffset"), 
               vertical_offset_left, 
               vertical_offset_right, 
               vertical_align_profiles,
               dihedral)

        machine.gc.normalize()

        return machine.gc
