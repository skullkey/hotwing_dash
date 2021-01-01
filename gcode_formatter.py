from __future__ import division
from hotwing_core.gcode_formatters.base import GcodeFormatterBase
import logging
logging.getLogger(__name__)

class CustomGcodeFormatter(GcodeFormatterBase):

    def __init__(self, parent, axis_mapping, hotwire_on, hotwire_off, prepend):
        super().__init__(parent)
        self.axis_mapping = {f:to for (f,to) in zip(['x','y','u','v'],axis_mapping.split(","))}
        self.hotwire_on = hotwire_on
        self.hotwire_off = hotwire_off
        self.prepend = prepend


    def process_command(self, command):
        c = command.data
        if command.type_ == "MOVE":
            return self.process_move(command)
        elif command.type_ == "FAST_MOVE":
            return self.process_fast_move(command)
        elif command.type_ == "DWELL":
            return self.process_dwell(command)
        else:
            self._log_unrecognized_command(command)
            return ""

    def process_dwell(self, command):
        return "G4 P%.4f" % command.data['p']

    def process_move(self,command):
        d = command.data
        am = self.axis_mapping

        cmd_list = ['G1']
        for ax in ['x','y','u','v']:
            if ax in d:
                cmd_list.append("%s%.10f" % (am[ax],d[ax]))
        return " ".join(cmd_list)

    def process_fast_move(self, command):
        d = command.data
        am = self.axis_mapping 
        cmd_list = ['G0']
        for ax in ['x','y','u','v']:
            if ax in d:
                cmd_list.append("%s%.10f" % (am[ax],d[ax]))
        return " ".join(cmd_list)

    def start_commands(self):
        out = []
        if self.prepend is not None:
            out.extend(self.prepend.split("\n"))

        # Set feedrate
        out.append("F%s" % self.parent.feedrate)

        ## Working Plane
        out.append("G17") # is this necessary?

        # Units        
        if self.parent.units.lower() == "inches":
            out.append("G20")
        elif self.parent.units.lower() == "millimeters":
            out.append("G21")
        else:
            out.append("(Unknown units '%s' specified!)" % self.parent.units)

        ## Absolute Mode
        out.append("G90")

        # Control path mode
        # G64 - Set Blended Path Control Mode
        # Set path tolerance using P value
        if self.parent.units.lower() == "inches":
            out.append("G64 P%.6f" % (1.0/64) )
        elif self.parent.units.lower() == "millimeters":
            out.append("G64 P%.2f" % (0.5) )
        

        # Use first work offset
        out.append("G54")

        if self.hotwire_on is not None:
            out.append(self.hotwire_on)

        return out

    def end_commands(self):
        out = []
        if self.hotwire_off is not None:
            out.append(self.hotwire_off)

        # End Program
        out.append("M30")
        return out