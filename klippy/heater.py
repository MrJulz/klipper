# Printer heater support
#
# Copyright (C) 2016  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import math, logging, threading

# Available sensors
Sensors = {
    # Common thermistors and their Steinhart-Hart coefficients
    "EPCOS 100K B57560G104F": (
        "thermistor",
        0.000722136308968056, 0.000216766566488498, 8.92935804531095e-08),
    "ATC Semitec 104GT-2": (
        "thermistor",
        0.000809651054275124, 0.000211636030735685, 7.07420883993973e-08),
    # Linear style conversion chips and their gain/offset
    "AD595": ("linear", 300.0 / 3.022, 0.),
}

SAMPLE_TIME = 0.001
SAMPLE_COUNT = 8
REPORT_TIME = 0.300
PWM_CYCLE_TIME = 0.100
KELVIN_TO_CELCIUS = -273.15
MAX_HEAT_TIME = 5.0
AMBIENT_TEMP = 25.
PID_PARAM_BASE = 255.

class error(Exception):
    pass

class PrinterHeater:
    error = error
    def __init__(self, printer, config):
        self.name = config.section
        sensor_params = config.getchoice('sensor_type', Sensors)
        self.is_linear_sensor = (sensor_params[0] == 'linear')
        if self.is_linear_sensor:
            adc_voltage = config.getfloat('adc_voltage', 5., above=0.)
            self.sensor_coef = sensor_params[1] * adc_voltage, sensor_params[2]
        else:
            pullup = config.getfloat('pullup_resistor', 4700., above=0.)
            self.sensor_coef = sensor_params[1:] + (pullup,)
        self.min_temp = config.getfloat('min_temp', minval=0.)
        self.max_temp = config.getfloat('max_temp', above=self.min_temp)
        self.min_extrude_temp = config.getfloat(
            'min_extrude_temp', 170., minval=self.min_temp, maxval=self.max_temp)
        self.max_power = config.getfloat('max_power', 1., above=0., maxval=1.)
        self.can_extrude = (self.min_extrude_temp <= 0.
                            or printer.mcu.is_fileoutput())
        self.lock = threading.Lock()
        self.last_temp = 0.
        self.last_temp_time = 0.
        self.target_temp = 0.
        algos = {'watermark': ControlBangBang, 'pid': ControlPID}
        algo = config.getchoice('control', algos)
        heater_pin = config.get('heater_pin')
        sensor_pin = config.get('sensor_pin')
        if algo is ControlBangBang and self.max_power == 1.:
            self.mcu_pwm = printer.mcu.create_digital_out(
                heater_pin, MAX_HEAT_TIME)
        else:
            self.mcu_pwm = printer.mcu.create_pwm(
                heater_pin, PWM_CYCLE_TIME, 0, MAX_HEAT_TIME)
        self.mcu_adc = printer.mcu.create_adc(sensor_pin)
        adc_range = [self.calc_adc(self.min_temp), self.calc_adc(self.max_temp)]
        self.mcu_adc.set_minmax(SAMPLE_TIME, SAMPLE_COUNT,
                                minval=min(adc_range), maxval=max(adc_range))
        self.mcu_adc.set_adc_callback(REPORT_TIME, self.adc_callback)
        self.control = algo(self, config)
        # pwm caching
        self.next_pwm_time = 0.
        self.last_pwm_value = 0
    def set_pwm(self, read_time, value):
        if self.target_temp <= 0.:
            value = 0.
        if ((read_time < self.next_pwm_time or not self.last_pwm_value)
            and abs(value - self.last_pwm_value) < 0.05):
            # No significant change in value - can suppress update
            return
        pwm_time = read_time + REPORT_TIME + SAMPLE_TIME*SAMPLE_COUNT
        self.next_pwm_time = pwm_time + 0.75 * MAX_HEAT_TIME
        self.last_pwm_value = value
        logging.debug("%s: pwm=%.3f@%.3f (from %.3f@%.3f [%.3f])" % (
            self.name, value, pwm_time,
            self.last_temp, self.last_temp_time, self.target_temp))
        self.mcu_pwm.set_pwm(pwm_time, value)
    # Temperature calculation
    def calc_temp(self, adc):
        if self.is_linear_sensor:
            gain, offset = self.sensor_coef
            return adc * gain + offset
        c1, c2, c3, pullup = self.sensor_coef
        r = pullup * adc / (1.0 - adc)
        ln_r = math.log(r)
        temp_inv = c1 + c2*ln_r + c3*math.pow(ln_r, 3)
        return 1.0/temp_inv + KELVIN_TO_CELCIUS
    def calc_adc(self, temp):
        if temp is None:
            return None
        if self.is_linear_sensor:
            gain, offset = self.sensor_coef
            return (temp - offset) / gain
        c1, c2, c3, pullup = self.sensor_coef
        temp -= KELVIN_TO_CELCIUS
        temp_inv = 1./temp
        y = (c1 - temp_inv) / (2*c3)
        x = math.sqrt(math.pow(c2 / (3.*c3), 3.) + math.pow(y, 2.))
        r = math.exp(math.pow(x-y, 1./3.) - math.pow(x+y, 1./3.))
        return r / (pullup + r)
    def adc_callback(self, read_time, read_value):
        temp = self.calc_temp(read_value)
        with self.lock:
            self.last_temp = temp
            self.last_temp_time = read_time
            self.can_extrude = (temp >= self.min_extrude_temp)
            self.control.adc_callback(read_time, temp)
        #logging.debug("temp: %.3f %f = %f" % (read_time, read_value, temp))
    # External commands
    def set_temp(self, print_time, degrees):
        if degrees and (degrees < self.min_temp or degrees > self.max_temp):
            raise error("Requested temperature (%.1f) out of range (%.1f:%.1f)"
                        % (degrees, self.min_temp, self.max_temp))
        with self.lock:
            self.target_temp = degrees
    def get_temp(self):
        with self.lock:
            return self.last_temp, self.target_temp
    def check_busy(self, eventtime):
        with self.lock:
            return self.control.check_busy(eventtime)
    def start_auto_tune(self, temp):
        with self.lock:
            self.control = ControlAutoTune(self, self.control, temp)


######################################################################
# Bang-bang control algo
######################################################################

class ControlBangBang:
    def __init__(self, heater, config):
        self.heater = heater
        self.max_delta = config.getfloat('max_delta', 2.0, above=0.)
        self.heating = False
    def adc_callback(self, read_time, temp):
        if self.heating and temp >= self.heater.target_temp+self.max_delta:
            self.heating = False
        elif not self.heating and temp <= self.heater.target_temp-self.max_delta:
            self.heating = True
        if self.heating:
            self.heater.set_pwm(read_time, self.heater.max_power)
        else:
            self.heater.set_pwm(read_time, 0.)
    def check_busy(self, eventtime):
        return self.heater.last_temp < self.heater.target_temp-self.max_delta


######################################################################
# Proportional Integral Derivative (PID) control algo
######################################################################

class ControlPID:
    def __init__(self, heater, config):
        self.heater = heater
        self.Kp = config.getfloat('pid_Kp') / PID_PARAM_BASE
        self.Ki = config.getfloat('pid_Ki') / PID_PARAM_BASE
        self.Kd = config.getfloat('pid_Kd') / PID_PARAM_BASE
        self.min_deriv_time = config.getfloat('pid_deriv_time', 2., above=0.)
        imax = config.getfloat('pid_integral_max', heater.max_power, minval=0.)
        self.temp_integ_max = imax / self.Ki
        self.prev_temp = AMBIENT_TEMP
        self.prev_temp_time = 0.
        self.prev_temp_deriv = 0.
        self.prev_temp_integ = 0.
    def adc_callback(self, read_time, temp):
        time_diff = read_time - self.prev_temp_time
        # Calculate change of temperature
        temp_diff = temp - self.prev_temp
        if time_diff >= self.min_deriv_time:
            temp_deriv = temp_diff / time_diff
        else:
            temp_deriv = (self.prev_temp_deriv * (self.min_deriv_time-time_diff)
                          + temp_diff) / self.min_deriv_time
        # Calculate accumulated temperature "error"
        temp_err = self.heater.target_temp - temp
        temp_integ = self.prev_temp_integ + temp_err * time_diff
        temp_integ = max(0., min(self.temp_integ_max, temp_integ))
        # Calculate output
        co = self.Kp*temp_err + self.Ki*temp_integ - self.Kd*temp_deriv
        #logging.debug("pid: %f@%.3f -> diff=%f deriv=%f err=%f integ=%f co=%d" % (
        #    temp, read_time, temp_diff, temp_deriv, temp_err, temp_integ, co))
        bounded_co = max(0., min(self.heater.max_power, co))
        self.heater.set_pwm(read_time, bounded_co)
        # Store state for next measurement
        self.prev_temp = temp
        self.prev_temp_time = read_time
        self.prev_temp_deriv = temp_deriv
        if co == bounded_co:
            self.prev_temp_integ = temp_integ
    def check_busy(self, eventtime):
        temp_diff = self.heater.target_temp - self.heater.last_temp
        return abs(temp_diff) > 1. or abs(self.prev_temp_deriv) > 0.1


######################################################################
# Ziegler-Nichols PID autotuning
######################################################################

TUNE_PID_DELTA = 5.0

class ControlAutoTune:
    def __init__(self, heater, old_control, target_temp):
        self.heater = heater
        self.old_control = old_control
        self.target_temp = target_temp
        self.heating = False
        self.peaks = []
        self.peak = 0.
        self.peak_time = 0.
    def adc_callback(self, read_time, temp):
        if self.heating and temp >= self.target_temp:
            self.heating = False
            self.check_peaks()
        elif not self.heating and temp <= self.target_temp - TUNE_PID_DELTA:
            self.heating = True
            self.check_peaks()
        if self.heating:
            self.heater.set_pwm(read_time, self.heater.max_power)
            if temp < self.peak:
                self.peak = temp
                self.peak_time = read_time
        else:
            self.heater.set_pwm(read_time, 0.)
            if temp > self.peak:
                self.peak = temp
                self.peak_time = read_time
    def check_peaks(self):
        self.peaks.append((self.peak, self.peak_time))
        if self.heating:
            self.peak = 9999999.
        else:
            self.peak = -9999999.
        if len(self.peaks) < 4:
            return
        temp_diff = self.peaks[-1][0] - self.peaks[-2][0]
        time_diff = self.peaks[-1][1] - self.peaks[-3][1]
        max_power = self.heater.max_power
        Ku = 4. * (2. * max_power) / (abs(temp_diff) * math.pi)
        Tu = time_diff

        Kp = 0.6 * Ku
        Ti = 0.5 * Tu
        Td = 0.125 * Tu
        Ki = Kp / Ti
        Kd = Kp * Td
        logging.info("Autotune: raw=%f/%f Ku=%f Tu=%f  Kp=%f Ki=%f Kd=%f" % (
            temp_diff, max_power, Ku, Tu,
            Kp * PID_PARAM_BASE, Ki * PID_PARAM_BASE, Kd * PID_PARAM_BASE))
    def check_busy(self, eventtime):
        if self.heating or len(self.peaks) < 12:
            return True
        self.heater.control = self.old_control
        return False


######################################################################
# Tuning information test
######################################################################

class ControlBumpTest:
    def __init__(self, heater, old_control, target_temp):
        self.heater = heater
        self.old_control = old_control
        self.target_temp = target_temp
        self.temp_samples = {}
        self.pwm_samples = {}
        self.state = 0
    def set_pwm(self, read_time, value):
        self.pwm_samples[read_time + 2*REPORT_TIME] = value
        self.heater.set_pwm(read_time, value)
    def adc_callback(self, read_time, temp):
        self.temp_samples[read_time] = temp
        if not self.state:
            self.set_pwm(read_time, 0.)
            if len(self.temp_samples) >= 20:
                self.state += 1
        elif self.state == 1:
            if temp < self.target_temp:
                self.set_pwm(read_time, self.heater.max_power)
                return
            self.set_pwm(read_time, 0.)
            self.state += 1
        elif self.state == 2:
            self.set_pwm(read_time, 0.)
            if temp <= (self.target_temp + AMBIENT_TEMP) / 2.:
                self.dump_stats()
                self.state += 1
    def dump_stats(self):
        out = ["%.3f %.1f %d" % (time, temp, self.pwm_samples.get(time, -1.))
               for time, temp in sorted(self.temp_samples.items())]
        f = open("/tmp/heattest.txt", "wb")
        f.write('\n'.join(out))
        f.close()
    def check_busy(self, eventtime):
        if self.state < 3:
            return True
        self.heater.control = self.old_control
        return False
