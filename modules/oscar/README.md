# Glyph OSCAR

**Portable Amateur Satellite Tracking for the Field**

Glyph OSCAR is a self-contained amateur satellite tracking and pass prediction tool designed specifically for portable operations.

Rather than requiring a laptop running Gpredict or other software, Glyph OSCAR provides a dedicated display that can be mounted to a tripod, set on a picnic table, attached to a backpack, or used alongside a handheld radio and directional antenna.

The goal is simple:

> Spend less time looking at software and more time working satellites.

---

## Features

* Live satellite pass prediction
* GPS positioning
* Maidenhead grid square positioning
* Manual coordinate entry
* Live compass skyplot
* Real-time azimuth and elevation display
* AOS / LOS timing
* Maximum elevation prediction
* Satellite frequency reference
* Operating notes
* Offline operation after TLE download
* Designed for handheld Yagi operation

---

## Example Use Case

A typical portable AMSAT station might consist of:

* HT
* Arrow Antenna
* Tape Measure Yagi
* Elk Antenna
* Homebrew Yagi

and a smartphone or laptop running satellite tracking software.

Glyph OSCAR replaces the need to continuously reference a phone or laptop that can be unwieldy by providing a dedicated display showing:

* Where the satellite currently is
* Where it is going
* How high it is
* How long the pass remains active

The operator simply points the antenna at the satellite marker and works the pass.

---

# Hardware

## Minimum Hardware

* Raspberry Pi Zero 2 W (recommended)
* GPIO Header Installed
* MicroSD Card (64GB recommended)
* 5V USB Power Source

## Display

Tested with:

* 3.5 Inch 480x320 Touch Screen TFT LCD SPI Display Panel

The display connects directly to the GPIO header and operates as the primary field display.

Other framebuffer-compatible displays may work.

## Optional GPS

Tested with:

* HiLetgo VK172 G-Mouse USB GPS/GLONASS Receiver

When connected, Glyph OSCAR can automatically determine operating location.

If GPS is unavailable, Maidenhead grid entry is supported.

## Optional USB Hub

Tested with:

* MakerSpot MicroUSB 4-Port OTG Hub

Useful when operating with:

* GPS receiver
* Keyboard
* Additional accessories

simultaneously.

---

# 3D Printed Enclosure

Included STL files:

```text
Glyph Screen Front.stl
Glyph Screen Back.stl
```

These files provide a compact enclosure for the Pi and display.

The enclosure is designed to:

* Protect the display
* Improve portability
* Support field operations
* Fit in a backpack or go-kit

---

# Software Requirements

Operating System:

* Raspberry Pi OS Lite (recommended)

Update system:

```bash
sudo apt update
sudo apt upgrade
```

Install required packages:

```bash
sudo apt install \
    python3 \
    python3-pil \
    python3-requests \
    python3-serial \
    python3-pip \
    fbi
```

---

# Skyfield Installation

Recent Raspberry Pi OS versions use PEP 668 protections.

If normal pip installation fails:

```bash
python3 -m venv ~/glyph-venv
source ~/glyph-venv/bin/activate

pip install skyfield
```

Verify:

```bash
python3 -c "import skyfield; print('OK')"
```

---

# Installation

Create directory:

```bash
mkdir -p ~/images
mkdir glyph-oscar
cd glyph-oscar
```

Copy files:

```text
glyph-oscar.py
~/images/glyph-compass.png
```

Make executable:

```bash
chmod +x glyph-oscar.py
```

Launch:

```bash
python3 glyph-oscar.py
```

---

# First Run

## Method 1: GPS

Connect GPS receiver.

Select:

```text
Set Location
Get GPS Fix
```

The program will attempt to determine location automatically.

---

## Method 2: Maidenhead Grid

If GPS is unavailable, in the menu use:

```text
Set Location ->
Enter Maidenhead Grid
```

Examples:

```text
DN13
DN13so
EM73
EM73tx
CM87
```

This method is accurate enough for handheld satellite operation.

---

## Method 3: Manual Coordinates

Latitude and longitude may also be entered manually.

---

# Live Pass Assist

The Live Pass Assist display is the primary operating screen.

## Compass Display

```text
North = Top
East  = Right
South = Bottom
West  = Left
```

## Pass Path

Yellow line:

```text
Predicted satellite path
```

## Satellite Marker

Orange marker:

```text
Current satellite position
```

## Altitude

The display uses a skyplot projection.

```text
Outer ring = Horizon
Center     = Overhead (90°)
```

The closer the satellite is to the center, the higher it is in the sky.

---

# Controls

```text
Enter = Refresh
a     = Auto Refresh
d     = Pass Details
b     = Back
```

---

# Internet Requirements

Internet is required for:

* TLE downloads

Internet is NOT required for:

* Pass prediction
* Live tracking
* GPS operation
* Compass display

Once TLE data has been downloaded, the system may be used completely offline.

This makes Glyph OSCAR ideal for:

* Parks
* Summits
* Campgrounds
* Field Day
* Portable AMSAT operations

Good idea: Do a TLE update as close to operation as possible for latest sat telemetry

---

# Future Development

Potential future features:

* Doppler shift assistance
* CAT control integration
* Hamlib support
* Additional satellite metadata
* Rotor control
* Expanded display options

---

# Troubleshooting

## No GPS Fix

Try:

* Moving outdoors
* Waiting several minutes for satellite acquisition
* Using Maidenhead grid entry

## Compass Image Missing

Verify:

```text
glyph-compass.png
```

exists in the expected location.

/home/YOUR_HOME_DIR_NAME/images/glyph-compass.png

## No Upcoming Passes

Check:

* Internet connectivity
* TLE download status
* Selected satellite
* Location configuration

---

# Disclaimer

This software is provided as-is.

The operator is responsible for verifying:

* Satellite status
* Frequencies
* Operating mode
* Licensing requirements

before transmitting.

---

73,

**Caleb // W4XEN**

Creator of Glyph Field Pi

---
