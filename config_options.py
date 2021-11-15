

import configparser
from io import StringIO
import numexpr
import math


def axis_mapping(input_str):
    return len(input_str.split(","))==4

class Config():
    def __init__(self, filename = None):
    
        ## Setup Config Parser
        self.config = configparser.ConfigParser()
        self.config.optionxform = lambda option: option

        self.CONFIG_OPTIONS = {
                'Project':{
                                "Units":{"type":str,"required":False,"default":"millimeters", "domain":["millimeters"]},
                                "Name":{"type":str,"required":False,"default":""},
                },
                'RootChord':{   "Profile":{"type":str,"required":True},
                                "ProfileThickness":{"type": float, "required": False, "default":0},
                                "Width":{"type":float,"required":True},
                                "LeadingEdgeOffset":{"type":float,"required":False,"default":0},
                                "Rotation":{"type":float,"required":False,"default":0},
                                "RotationPosition":{"type":float,"required":False,"default":0}
                            },
                'TipChord':{    "Profile":{"type":str,"required":True},
                                "ProfileThickness":{"type": float, "required": False, "default":0},
                                "Width":{"type":float,"required":True},
                                "LeadingEdgeOffset":{"type":float,"required":False,"default":0},
                                "Rotation":{"type":float,"required":False,"default":0},
                                "RotationPosition":{"type":float,"required":False,"default":0}
                },
                'Panel':{
                                "Bottom":{"type":float,"required":False, "default":0.0},
                                "Height":{"type":float,"required":True},
                                "Depth":{"type":float,"required":False, "default":600.0},
                                "Inset":{"type":float,"required":False, "default":0.0},
                                "SafeHeight":{"type":float,"required":False, "default":0}
                },
                 'Wing':{
                                "TipChordSide":{"type":str, "required":False, "default":"right", "domain":["left","right"]},
                                "Width":{"type":float,"required":True},

                                "Inverted":{"type":bool, "required":False, "default":False},
                                "Dihedral":{"type":float,"required":False, "default":0.0},
                                "VerticalAlignProfiles":{"type":str,"required":False, "default": "default", "domain":["default","bottom","dihedral"]}, 
                                "StockLeadingEdge":{"type":float,"required":False,"default":0},
                                "StockTrailingEdge":{"type":float,"required":False,"default":0},
                                "StockTrailingEdgeAngle":{"type":float,"required":False,"default":0},

                                "SheetingTop":{"type":float,"required":False,"default":0},
                                "SheetingBottom":{"type":float,"required":False,"default":0},                  
                },
                'Placement':{
                                "RootChordOffset":{"type":float,"required":True},
                                "HorizontalOffset":{"type":float,"required":False, "default": 0},                    
                                "VerticalOffsetRoot":{"type":float,"required":False, "default": 25},                    
                                "VerticalOffsetTip":{"type":float,"required":False, "default": None},                    
                                "RotateWing":{"type":bool,"reqruied":False,"default":False}
                },

                'Machine':{
                                "Width":{"type":float,"required":True},
                                "Height":{"type":float,"required":False, "default": 600},
                                "Depth":{"type":float,"required":True},

                                "Feedrate":{"type":float,"required":True},
                                "Kerf":{"type":str,"required":True},
                },

               
                'Gcode':{
                                "GcodeWireOn" : {"type":str,"required":False,"default":None},
                                "GcodeWireOff" : {"type":str,"required":False,"default":None},
                                "AxisMapping" : {"type":str,"required":False,"default":"X,Y,Z,A","validate":axis_mapping},
                                "ConfigAsComment" : {"type":bool,"required":False,"default":True},
                                "InterpolationPoints": {"type":int, "required":False, "default": 200}


                }
            }

        self.filename = filename
        if filename is not None:
            self.read_config(self.filename)

    def get_config(self, section, parameter):
        opt = self.CONFIG_OPTIONS[section][parameter]
        try:
            if opt['type'] == float:
                v = self.config.get(section,parameter)
                v = numexpr.evaluate(v).item()
                return float(v)
            elif opt['type'] == str:
                return self.config.get(section,parameter) 
            elif opt['type'] == int:
                v = self.config.get(section,parameter)
                v = numexpr.evaluate(v).item()
                return int(v) 
            elif opt['type'] == bool:
                return self.config.getboolean(section,parameter)
            else:
                print("ERROR PARSING CONFIG OPTION")
        except configparser.NoOptionError:
            if opt['required']:
                raise
            else:   
                return opt["default"]

    def read_config(self, filename):
        with open(filename) as f:
            config_string = f.read()
        self.read_string(config_string)

    def validate_config(self, config_string):
        c = self.get_config
        result = []
        current_section = ""

        lines = config_string.split("\n")
        for i,l in enumerate(lines):
            section = self.config.SECTCRE.findall(l)
            option = self.config.OPTCRE.findall(l)
            if len(section) == 1:
                current_section = section[0]
                if current_section not in self.CONFIG_OPTIONS:
                    result.append(f"Unrecognized section:{s} on line {i+1}")

            elif len(option) == 1:
                key, _, value = option[0]
                if key not in self.CONFIG_OPTIONS[current_section]:
                    result.append(f"Unrecognized key for [{current_section}]:{key} on line {i+1}")
                else:
                    type_ = self.CONFIG_OPTIONS[current_section][key]["type"]
                    domain = self.CONFIG_OPTIONS[current_section][key].get("domain", None)
                    validator = self.CONFIG_OPTIONS[current_section][key].get("validate", None)
                    if type_ == bool:
                        domain = ["yes","no"]

                    if domain is not None:
                        if value not in domain:
                            result.append(f"Unrecognized value for [{current_section}],{key}:{value} on line {i+1}.  Valid options:{domain}")
                    elif validator is not None:
                        if not validator(value):
                            result.append(f"Invalid value for [{current_section}],{key}:{value} on line {i+1}.  ")
                    else:
                        try:
                            if type_ in [int, float]:
                                test = type_(numexpr.evaluate(value).item())
                            else:
                                test = type_(value)
                        except:
                            result.append(f"Unparseable value for [{current_section}],{key}:{value} on line {i+1}.  Valid options:{str(type_)}")



        for section in self.CONFIG_OPTIONS:
            for key in self.CONFIG_OPTIONS[section]:
                try:
                    test = self.get_config(section, key)
                except: # configparser.NoOptionError:
                    result.append(f"Value for [{section}],{key} is required.")



        return result

    def read_string(self, config_string):
        self.config.clear()
        self.config.read_string(config_string)
        result = self.validate_config(config_string)
        return result


    def config_as_str(self):
        output = StringIO()
        self.config.write(output)
        contents = output.getvalue()
        output.close()  
        return contents
        