
# Hotwing Slicer

Config and Gcode visualizer for the [hotwing-cli](https://github.com/jasonhamilton/hotwing-cli) and [hotwing-core library](https://github.com/jasonhamilton/hotwing-core).  Also the tutorial below based on hotwing-cli. 

Mostly uses hotwing-core, with some changes:

* alternative cutting strategy - trailing edge first
* all hotwing-cli command line options now part of config
* additional config options (see Gcode section below)
* visualization using Plotly
* website using Dash

# Example Wing 

This alternative Wiesel wing design from https://www.rcgroups.com/forums/showthread.php?1456458-Wisel-just-the-glider-you-need:

![Whole Wing](/static/wing_plan_full.png)

The wingspan is 900mm, the root chord is 330mm and the tip chord is 180mm.  In HotWing we work with wing halves, so let's see what that looks like.

![Half Wing](/static/wing_plan_half.png)


# Example Config File

## Project

For this project we we'll be working in inches, so in the Project section we will specify the units.

```cfg
[Project]
Name = Example Config
Units = millimeters
...
```
**Name** - Used to generate the config filename when downloading ("Example Config.txt") and the filename for gcode ("Example Config.gcode"). 

**Units** - Defines the project to be in 'inches' or 'millimeters'.  Default is inches if not specified.

## RootChord

According to the wing plan the profile is a PW-1211, a quick Google search finds it here http://airfoiltools.com/airfoil/details?airfoil=pw1211-pw :  

![Profile](/static/pw-1211.png)

This is a very useful site - note at the bottom righthand side are links for both Selig and Lednicer coordinate files (both supported by Hotwing).


```cfg
...
[RootChord]
Profile = http://airfoiltools.com/airfoil/seligdatfile?airfoil=pw1211-pw
Width = 330
LeadingEdgeOffset = 0
Rotation = 0
RotationPosition = 0.5
```

**Profile** - The profile is a URL to the airfoil coordinates. The software accepts Selig and Lednicer type coordinates files

**Width** - We know the width from the design above is 330mm at the root.

**LeadingEdgeOffset** - We want the tip of the airfoil to be at 0 - I.E. we don't want to move it.

**Rotation** - Leave this at 0.  I don't want to rotate this chord.

**RotationPosition** - This doesn't matter since the Rotation Parameter is 0.


## TipChord

Now let's modify the tip chord.  Similar to the Root but let's take a look at some of the other Parameters.

```cfg
...
[TipChord]
Profile = http://airfoiltools.com/airfoil/seligdatfile?airfoil=pw1211-pw
Width = 180
LeadingEdgeOffset = 100
Rotation = -1
RotationPosition = 0.25
...
```

**LeadingEdgeOffset** - To get the shape that we want we need to define the LeadingEdgeOffset.  If we don't define the LeadingEdgeOffset, the leading edge's will be straignt and the trailing edge will sweep forward like this:

![Offset Example 1](/static/straigh_le.png)

From the wing plan, the LE-sweep is 100mm - in Hotwing terms this is the LeadingEdgeOffset:



![Offset Example 2](/static/wisel_le.png)


**Rotation** - For this design we need 1 degree of washout on the tip, so I need to set the Rotation Parameter to -1.  This will angle the tip downward by 1 degree.  To angle the tip upward, use a positive number.

**RotationPosition** - Since the Rotation value is now being used, the RotationPosition will be takend into account.  This value is the point along the chord (measured from front to back) where the foil will be rotated.  A value of 0.25 tells HotWing to rotate the foil around a point at 25% of the chord distance.  Since our chord is 7 inches long, the rotation will occur 1.75 (25%\*7) inches back from the tip of the foil.

## Panel

```cfg
...
[Panel]
TipChordSide = left
RootChordOffset = 300
Width = 450
Bottom = 0
Height = 50
Inset = 0
Depth = 490
SafeHeight = 60
...
```

**TipChordSide** - [New] Determines if we are cutting the left hand wing (TipChordSide = left) or the right hand wing (TipChordSide = right).  In hotwing-cli this is a command line option.  Valid options are "left" and "right".

**RootChordOffset** - [New] Determines the left/right (z axis in picture below) placement of the panel on the machine.  The offset here refers to the distance to the pillar closest to the root chord.  So, if the TipChordSide = left, then the distance is between the RootChord and the right-hand pillar.

![Hotwire machine axes](/static/hotwire_machine.png)

**Width** - The total width of the half wing. 

**Bottom** - Placement or offset of the panel above the table (Y-axis in picture)

**Height** - Thickness or height of the panel

**Inset** - Placement or offset of the panel away from the edge (X-axis in picture)

**Depth** - Depth of the panel, i.e. measurement of the panel along the X-axis in the picture

**SafeHeight** - Height (from 0) the foam wire can safely move above the panel when for instance cutting the trailing edge

## Wing

```cfg
...
[Wing]
HorizontalOffset = 0
VerticalOffsetRoot = 25
VerticalOffsetTip = 25
VerticalAlignProfiles = default
StockLeadingEdge = 0
StockTrailingEdge = 50
SheetingTop = 0.0
SheetingBottom = 0.0
...
```

**HorizontalOffset** - [New] Min distance between the trailing edge and zero position on the X-axis (in machine picture)

**VerticalOffsetRoot** - [New] Min distance between the trailing edge and zero position on the Y-axis (in machine picture) for the Root Profile.  

For example, in the following profile view, the HorizontalOffset = 20 and the VerticalOffsetRoot = 25

![offsets](/static/horz_vert_offset.png)

Similarly in plan view, with RootChordOffset=300 and HorizontalOffset=20:

![plan offsets](/static/horz_vert_offset_plan.png)

Note that if the HorizontalOffset leads to an infeasible cut (i.e. negative machine axes), the settings will be ignored.  This is illustrated below, the yellow lines represents the extremes of the cutting path and already at 0, so any setting of HorizontalOffset below 20 will be ignore:

![plan offset cutpath](/static/horz_vert_offset_plan_cutpath.png)

**VerticalOffsetTip** - [New] Similar to VerticalOffsetRoot, except for the tip profile, useful for cutting dihedral into the wing.  This setting is optional and if omitted, the offset is determined by the **VerticalAlignProfiles**

**VerticalAlignProfiles** - Used in the case when VerticalOffsetTip is omitted.  Two options are available "default" and "bottom".  "default" aligns the chords of the Tip and Root profile.  "bottom" aligns the lowest points.

For example the following two figures shows default alignment:

![align default](/static/align_default.png)

and bottom alignment:

![align bottom](/static/align_bottom.png)

**StockLeadingEdge** - The stock leading edge is an allowance for a piece of wood stock that will be glued on the leading edge to give it additional strength.  This wood will then be sanded by hand to the shape of the airfoil.  This wing will use a 0.5" x 0.5" piece of stock, so the StockLeadingEdge parameter is set to 0.5.  You can set this to a lower number if you want some additional allowance, say 0.4".  The software simply trims the indicated amount from the leading edge of the wing.

**StockTrailingEdge** - The StockTrailingEdge parameter is similar to StockLeadingEdge, except it is trimmed from the trailing edge instead.  Typically you'll use aileron stock here.  This amount is just measured from the trailing edge - it's up to you to make sure your stock will cover the specified area.

![Stock Example 1](https://raw.githubusercontent.com/jasonhamilton/hotwing-cli/master/img/tutorial_stock_1.png)

Now our cut foam will look like this:

![Stock Example 2](https://raw.githubusercontent.com/jasonhamilton/hotwing-cli/master/img/tutorial_stock_2.png)

And after we glue on and shape the stock we will end up with something like this:

![Stock Example 3](https://raw.githubusercontent.com/jasonhamilton/hotwing-cli/master/img/tutorial_stock_3.png)

**SheetingTop and SheetingBottom** - The next parameters that need to be set are SheetingTop and SheetingBottom.  These define an allowance for balsa, plywood, or other types of sheeting.  This wing will be sheeted with 1/16 inch balsa on the top and bottom, so I set these to 0.0625.  The sheeting can be visualized in this image:

![Sheeting Example](https://raw.githubusercontent.com/jasonhamilton/hotwing-cli/master/img/tutorial_sheeting.png)

## Machine

```cfg
...
[Machine]
Width = 1490
Height = 400
Depth = 490
Feedrate = 160
Kerf = 2
```

**Width** - Set Width to the width of your foam cutting machine.



**Feedrate** - CNC feedrate speed in units / minute.

**Kerf** - Kerf is the amount of room to offset the hotwire so an accurate amount of foam is cut.


```cfg
...
[Gcode]
GcodeWireOn = M3 S100
GcodeWireOff = M5
AxisMapping = X,Y,Z,A
ConfigAsComment = yes
InterpolationPoints = 200
...
```
