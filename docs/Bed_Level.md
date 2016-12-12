Calibrating the printer's bed is critical to getting high quality
prints. There are two goals in the calibration process - knowing the
distance between the head and bed, and making sure that distance is
constant at all points on the bed.

To get good results the bed should be level to within a few
microns. That's less than the width of a human hair. Relax though -
it's not difficult to accomplish this!

The key to leveling the bed accurately is to utilize the printer's
high precision stepper motors.

**Always level the bed to the stepper motors; never attempt to level
the bed by eye.**

To do this, one should create a gcode script and run that script to
move the stepper motors to precise locations. At each position, one
then adjusts the bed leveling screws so that the bed is a consistent
distance from the head at that position. In this way, the bed screws
are adjusted to the head (which is set by the stepper motors).

One must know the XY coordinates of each bed screw as the gcode script
will command the printer to those positions.  If a bed screw is not
under the bed platform, then use the XY position on the bed platform
that is closest to the screw.

As the print head stops above each bed screw, one should move a piece
of paper between the head and bed. The goal is to feel a tiny amount
of friction as the paper is moved around. The bed screw is then
adjusted until the desired friction (and thus the desired height) is
achieved. The exact amount of friction isn't important - what's
important is that similar friction is felt above all bed screws and
thus the bed is a consistent distance from the head.

**Always use a gcode script to level the bed; never level the bed by
manually jogging the print head.**

Using a gcode script to bed level is important as small differences in
process can lead to differences in results. These differences are
important at the micron scale. For example, on a cartesian printer,
even changing the ordering of homing can alter when the endstops
trigger (due to slight differences in torque on the carriages
resulting from different axis positions). By leveling with a script,
the results are repeatable and reproducible.

Similarly, changes in temperature lead to different results due to
thermal expansion.

**Always make sure the nozzle and bed are at room temperature before
leveling the bed.**

If either the bed or nozzle has been heated, then take a break for a
few minutes and wait for them to cool all the way down to room
temperature. Use the printer's temperature graph and verify that both
the bed and nozzle aren't changing and that both are under 40 degrees
Celsius.

Do inspect the nozzle head before bed leveling and make sure there is
no plastic on the nozzle. If there is, heat the nozzle, remove the
plastic with a metal tweezers and then wait for the nozzle to return
to room temperature. Double check that the nozzle is clean after it
cools.

Similarly, make sure there is to tape or other debris on the bed while
bed leveling.

**Always make sure the nozzle and bed are clean before leveling the
bed.**

To create the gcode script, start with this example:

```
; Start with bed and nozzle both cool and no tape on the bed.  Make
; sure there is no plastic on the nozzle.

; First home the axes
G28
M206 Z0
G90

; Move to front screw
G1 F800 Z5
G1 F4000 X97.1 Y77.5
G1 F400 Z0.1
M117 Adjust front screw so bed is .1mm from nozzle.
M0

; Move to rear screw
G1 F800 Z5
G1 F4000 X97.1 Y177.5
G1 F400 Z0.1
M117 Adjust rear screw so bed is .1mm from nozzle.
M0

; Move to right screw
G1 F800 Z5
G1 F4000 X147.1 Y127.5
G1 F400 Z0.1
M117 Adjust right screw so bed is .1mm from nozzle.
M0

; Set Z axis endstop position
M206 Z-0.08 ; 0.08 is for thermal expansion of the nozzle

; Lift Z
G1 F400 Z10
```

Update the above with the XY coordinates of the bed leveling screws on
the target printer. Then save the file as 'bedlevel.gcode' and upload
it to the printer. Each time one needs to bed level, just run the
"bedlevel.gcode" script.

During the bed leveling process, if it's necessary to adjust any of
the screws to obtain the desired amount of friction (and thus height),
then be sure to rerun the script upon completion. The final run of the
script should just confirm that the bed is in fact level.

If one looks closely, they'll see two interesting constants in the
above - one is 0.1mm for the width of a piece of paper and the other
is 0.08mm for thermal expansion. It's not necessary to calibrate the
width of a piece of paper, as any inaccuracy there can be accounted
for when calibrating for thermal expansion. Using 0.08 for thermal
expansion is a good starting value, but it can (and should) be further
calibrated for the target printer.

The best way to calibrate this value is to print an object and stop
the print after the first layer has been printed. Wait for the printer
and object to cool down. Then take a digital calipers and measure the
height of that first layer. It should match the first layer height
specified in the slicer for the object. If it's smaller, then there
was a larger amount of thermal expansion and if it's larger then there
was less thermal expansion. Adjust the thermal expansion in the
"bedlevel.gcode" script accordingly.

It is only necessary to calibrate for thermal expansion once. Update
the "bedlevel.gcode" with the new value and then use the resulting
"bedlevel.gcode" file for future bed leveling.

**It is necessary to run the M206 command each time the Klippy host
software is restarted!**
