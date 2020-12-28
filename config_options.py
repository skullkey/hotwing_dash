

import configparser

class Config():
    def __init__(self, filename = None):
    
        ## Setup Config Parser
        self.config = configparser.ConfigParser()

        self.CONFIG_OPTIONS = {
                'Project':{
                                "Units":{"type":str,"required":False,"default":"inches"},

                },
                'RootChord':{   "Profile":{"type":str,"required":True},
                                "Width":{"type":float,"required":True},
                                "LeadingEdgeOffset":{"type":float,"required":False,"default":0},
                                "Rotation":{"type":float,"required":False,"default":0},
                                "RotationPosition":{"type":float,"required":False,"default":0}
                            },
                'TipChord':{    "Profile":{"type":str,"required":True},
                                "Width":{"type":float,"required":True},
                                "LeadingEdgeOffset":{"type":float,"required":False,"default":0},
                                "Rotation":{"type":float,"required":False,"default":0},
                                "RotationPosition":{"type":float,"required":False,"default":0}
                },
                'Panel':{
                                "RootChordOffset":{"type":float,"required":True},
                                "TipChordSide":{"type":str, "required":False, "default":"right"},
                                "Width":{"type":float,"required":True},
                                "Bottom":{"type":float,"required":False, "default":0.0},
                                "Height":{"type":float,"required":True},
                                "Depth":{"type":float,"required":False, "default":600.0},
                                "Inset":{"type":float,"required":False, "default":0.0},
                                "SafeHeight":{"type":float,"required":False, "default":0},

                },
                 'Wing':{
                                "HorizontalOffset":{"type":float,"required":False, "default": 0},                    
                                "VerticalOffsetRoot":{"type":float,"required":False, "default": 25},                    
                                "VerticalOffsetTip":{"type":float,"required":False, "default": None},                    
                                "VerticalAlignProfiles":{"type":str,"required":False, "default": "default"}, 
                                "StockLeadingEdge":{"type":float,"required":False,"default":0},
                                "StockTrailingEdge":{"type":float,"required":False,"default":0},
                                "SheetingTop":{"type":float,"required":False,"default":0},
                                "SheetingBottom":{"type":float,"required":False,"default":0}                   
                },

                'Machine':{
                                "Width":{"type":float,"required":True},
                                "Height":{"type":float,"required":False, "default": 600},
                                "Depth":{"type":float,"required":True},

                                "Feedrate":{"type":float,"required":True},
                                "Kerf":{"type":str,"required":True},
                },

               
                'Gcode':{
                                "GcodeWireOn" : {"type":str,"required":False,"default":""},
                                "GcodeWireOff" : {"type":str,"required":False,"default":""},
                                "Axes" : {"type":str,"required":False,"default":"X,Y,Z,A"},
                                "ConfigAsComment" : {"type":str,"required":False,"default":"yes"},
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
                return self.config.getfloat(section,parameter)
            elif opt['type'] == str:
                return self.config.get(section,parameter) 
            elif opt['type'] == int:
                return self.config.getint(section,parameter)                 
            else:
                print("ERROR PARSING CONFIG OPTION")
        except configparser.NoOptionError:
            if opt['required']:
                raise
            else:   
                return opt["default"]

    def read_config(self, filename):
        self.config.read(filename)