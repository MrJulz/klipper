Klipper is currently in an experimental state. These instructions
assume the software will run on a Raspberry Pi computer in conjunction
with OctoPrint. Klipper supports Atmel ATmega based micro-controllers
and Arduino Due (Atmel SAM3x8e ARM micro-controllers) printers.

It is recommended that a Raspberry Pi 2 or Raspberry Pi 3 computer be
used as the host. The software will run on a first generation
Raspberry Pi, but the combined load of OctoPrint, Klipper, and a web
cam (if applicable) can overwhelm its CPU leading to print stalls.

Prepping an OS image
====================

Start by installing [OctoPi](https://github.com/guysoft/OctoPi) on the
Raspberry Pi computer. Use OctoPi v0.13.0 or later - see the
[octopi releases](https://github.com/guysoft/OctoPi/releases) for
release information. One should verify that OctoPi boots and that the
OctoPrint web server works. After connecting to the OctoPrint web
page, follow the prompt to upgrade OctoPrint to v1.3.0 or later.

After installing OctoPi and upgrading OctoPrint, ssh into the target
machine (ssh pi@octopi -- password is "raspberry") and run the
following commands:

```
sudo apt-get update
sudo apt-get install libncurses-dev libusb-dev
sudo apt-get install avrdude gcc-avr binutils-avr avr-libc # AVR toolchain
sudo apt-get install bossa-cli libnewlib-arm-none-eabi # ARM toolchain
```

The host software (Klippy) requires a one-time setup - run as the
regular "pi" user:

```
virtualenv ~/klippy-env
~/klippy-env/bin/pip install cffi==1.6.0 pyserial==3.2.1 greenlet==0.4.10
```

Building Klipper
================

To obtain Klipper, run the following command on the target machine:

```
git clone https://github.com/KevinOConnor/klipper
cd klipper/
```

To compile the micro-controller code, start by configuring it:

```
make menuconfig
```

Select the appropriate micro-controller and serial baud rate. Once
configured, run:

```
make
```

Ignore any warnings you may see about "misspelled signal handler" (it
is due to a bug fixed in gcc v4.8.3).

Installing Klipper on an AVR micro-controller
---------------------------------------------

The avrdude package can be used to install the micro-controller code
on an AVR ATmega chip. The exact syntax of the avrdude command is
different for each micro-controller. The following is an example
command for atmega2560 chips:

```
example-only$ avrdude -C/etc/avrdude.conf -v -patmega2560 -cwiring -P/dev/ttyACM0 -b115200 -D -Uflash:w:/home/pi/klipper/out/klipper.elf.hex:i
```

Installing Klipper on an Arduino Due
------------------------------------

Klipper currently uses the Arduino Due USB programming port (it will
not work when connected to the application USB port). The programming
port is the USB port closest to the power supply. To flash Klipper to
the Due connect it to the host machine and run:

```
stty -F /dev/ttyACM0 1200
bossac -i -p ttyACM0 -R -e -w -v -b ~/klipper/out/klipper.bin
```

Setting up the printer configuration
====================================

It is necessary to configure the printer. This is done by modifying a
configuration file that resides on the host. Start by copying an
example configuration and editing it.  For example:

```
cp ~/klipper/config/example.cfg ~/printer.cfg
nano printer.cfg
```

Make sure to look at and update each setting that is appropriate for
the hardware.

Configuring OctoPrint to use Klippy
===================================

The OctoPrint web server needs to be configured to communicate with
the Klippy host software. Using a web-browser, login to the OctoPrint
web page, and navigate to the Settings tab. Then configure the
following items:

Under "Serial Connection" in "Additional serial ports" add
"/tmp/printer". Then click "Save".

Enter the Settings tab again and under "Serial Connection" change the
"Serial Port" setting to "/tmp/printer". Change the Baudrate field to
250000 (this buad rate field is not related to the firmware baudrate
and may be safely left at 250000). Unselect the "Not only cancel
ongoing prints but also disconnect..." checkbox.

Under the "Features" tab, unselect "Enable SD support". Then click
"Save".

Running the host software
=========================

The host software is executed by running the following as the regular
"pi" user:

```
~/klippy-env/bin/python ~/klipper/klippy/klippy.py ~/printer.cfg -l /tmp/klippy.log < /dev/null > /dev/null 2>&1 &
```

Once Klippy is running, use a web-browser and navigate to the
OctoPrint web site. Under the "Connection" tab (on the left of the
main page) make sure the "Serial Port" is set to "/tmp/printer" and
click "Connect". (If "/tmp/printer" is not an available selection then
try reloading the page.)

Once connected, navigate to the "Terminal" tab and type "status"
(without the quotes) into the command entry box and click "Send". If
the Klippy config file was successfully read, and the micro-controller
was successfully found and configured, then this command will report
that the printer is ready. Klippy reports error messages via this
terminal tab. The "status" command can be used to re-report error
messages.

In addition to common g-code commands, Klippy supports a few extended
commands - "status" is an example of one of these commands. Use the
"help" command to get a list of other extended commands. In
particular, note the "restart" command - use this command to reload
the Klippy config file after any changes.
