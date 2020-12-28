from __future__ import division
from hotwing_core.profile import Profile
from hotwing_core.rib import Rib
from hotwing_core.machine import Machine
from hotwing_core.panel import Panel
from hotwing_core.coordinate import Coordinate
from hotwing_cli.config_options import CONFIG_OPTIONS, get_config, read_config
from hotwing_cli.validators import validate_side, vaidate_config_file, validate_trim, validate_kerf
from hotwing_core.gcode import Gcode


from importlib import reload

import trailing_cutting_strategy
reload(trailing_cutting_strategy)

import config_options
reload(config_options)

class GcodeGen():

    def __init__(self, config):
        self.config = config
        self.points = self.config.get_config('Gcode','InterpolationPoints')

    def gen_gcode(self):
        get_config = self.config.get_config
        root_offset =  get_config('Panel','RootChordOffset')
        side = get_config('Panel','TipChordSide')


        rib1 = Rib( get_config('RootChord',"Profile"), 
                            scale=get_config('RootChord',"Width"), 
                            xy_offset=Coordinate(get_config('RootChord',"LeadingEdgeOffset"),0), 
                            top_sheet=get_config('Wing',"SheetingTop"), 
                            bottom_sheet=get_config('Wing',"SheetingBottom"), 
                            front_stock=get_config('Wing',"StockLeadingEdge"), 
                            tail_stock=get_config('Wing',"StockTrailingEdge"),
                            rotation=get_config('RootChord',"Rotation"),
                            rotation_pos=get_config('RootChord',"RotationPosition"),
                            )

        rib2 = Rib( get_config('TipChord',"Profile"), 
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
            print("reversing")
            panel = Panel.reverse(panel)
            self.left_offset = root_offset
        else:
            self.left_offset = get_config('Machine',"Width") -  get_config('Panel',"Width") - root_offset

        if panel.width > get_config('Machine',"Width"):
                print("Error: Panel (%s) is bigger than the machine width (%s)." % (get_config('Machine',"Width"), panel.width) )

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

        cs = trailing_cutting_strategy.TrailingEdgeCuttingStrategy(machine)

        if side == "right":
            vertical_offset_left = get_config("Wing","VerticalOffsetRoot")
            vertical_offset_right = get_config("Wing","VerticalOffsetTip")
        else:
            vertical_offset_left = get_config("Wing","VerticalOffsetTip")
            vertical_offset_right = get_config("Wing","VerticalOffsetRoot")

        vertical_align_profiles = get_config("Wing","VerticalAlignProfiles")


        cs.cut(get_config("Wing","HorizontalOffset"), 
               vertical_offset_left, 
               vertical_offset_right, 
               vertical_align_profiles)

        return machine.gc
