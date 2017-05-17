# Printer servo support
#
# Copyright (C) 2017  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
#
# All time units are specified in Seconds
#

SERVO_SIGNAL_PERIOD = 0.020

class PrinterServo:
    def __init__(self, printer, config):
        self.last_pulsewidth = -1.
        self.mcu_servo = printer.mcu.create_pwm(
            config.get('servo_pin'), SERVO_SIGNAL_PERIOD, 0, 0.)
        self.MIN_PULSE_WIDTH = config.getfloat('minimum_pulse_width', 1) / 1000000.0
        self.MAX_PULSE_WIDTH = config.getfloat('maximum_pulse_width', 2) / 1000000.0
        self.MAX_ANGLE = config.getint('maximum_servo_angle', 180) 
        self.SIGNAL_WIDTH        = self.MAX_PULSE_WIDTH - self.MIN_PULSE_WIDTH
        self.DEGREES_PER_SECOND  = self.MAX_ANGLE / self.SIGNAL_WIDTH

    # External commands
    def set_pulsewidth(self, print_time, pulsewidth):
        pulsewidth = max(self.MIN_PULSE_WIDTH, min(self.MAX_PULSE_WIDTH, pulsewidth))
        if pulsewidth == self.last_pulsewidth: return
        dutycycle = pulsewidth / SERVO_SIGNAL_PERIOD
        mcu_time = self.mcu_servo.print_to_mcu_time(print_time)
        self.mcu_servo.set_pwm(mcu_time, dutycycle)
        self.last_pulsewidth = pulsewidth

    def set_angle(self, print_time, angle):
        angle = max(0., min(self.MAX_ANGLE, angle))
        pulsewidth = self.MIN_PULSE_WIDTH + (angle / self.DEGREES_PER_SECOND)
        self.set_pulsewidth(print_time, pulsewidth)

def add_printer_objects(printer, config):
    if config.has_section('servo'):
        printer.add_object('servo0', PrinterServo(printer, config.getsection('servo')))
        return
    for i in range(99):
        section = 'servo%d' % (i,)
        if not config.has_section(section):
            break
        printer.add_object(section, PrinterServo(printer, config.getsection(section)))

def get_printer_servos(printer):
    out = []
    for i in range(99):
        extruder = printer.objects.get('servo%d' % (i,))
        if extruder is None:
            break
        out.append(extruder)
    return out
