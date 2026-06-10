# Glyph

**Secure. Portable. Connected.**

Glyph is a modular field computer built on the Raspberry Pi platform and designed for amateur radio, weather information, intelligence, offline knowledge, navigation, communications, media, and off-grid operations.

Originally created as a simple internet radio player, Glyph has evolved into a collection of purpose-built tools that run on a compact battery-powered Raspberry Pi with a small display. The goal is simple:

> Build tools that are actually useful in the field.

Whether operating an amateur satellite, monitoring severe weather, listening to an audiobook, checking GPS position, activating a SOTA summit or a POTA park, receiving a Meshtastic message, or simply falling asleep to Swiss Classical Radio, Glyph provides a dedicated interface without relying on a phone, laptop, or cloud service.

---

## Philosophy

Glyph follows a few simple principles:

- Small enough to fit in a backpack
- Simple enough to operate over SSH or a mouse/keyboard in the field
- Useful without Internet access whenever possible
- Dedicated tools instead of one giant application
- Designed for real-world field use

Glyph is not intended to replace larger, purpose-built, or application-specfic systems.

Glyph is intended to supplement them.

---

## Current Modules

### Communications

- OSCAR Satellite Tracker
- SMS Tools
- Email Tools
- Radio Utilities
- Meshtastic Interface (in development)

### Weather & Intelligence

- NWS Weather
- Weather Radar
- Solar Weather
- News Reader
- Wiki Lookup
- GPT Assistant

### Navigation

- GPS Tools
- Maidenhead Grid Utilities
- POTA Spotter/Navigator

### Media

- Internet Radio
- Podcast Player
- Audiobook Player
- Audio Bible

### Utilities

- Speed Test
- Status Dashboard
- OTP Message Encryption
- Resistor Calculator
- System Utilities

---

## Featured Applications

### Glyph OSCAR

A portable AMSAT satellite pass predictor and live tracking display.

Features include:

- GPS positioning
- Maidenhead grid fallback
- Pass prediction
- Live pass assist
- Sky plot display
- Frequency reference information
- Offline operation after TLE download

Designed for handheld satellite operation with an HT and directional antenna.

### Glyph Weather

A graphical weather intelligence system featuring:

- Current conditions
- Forecasts
- NWS products
- Graphical radar imagery
- Day and night radar modes
- Local and wide-area views

### Glyph Solar Weather

Space weather information for amateur radio operators including:

- Solar flux
- K-index
- X-ray activity
- Solar imagery
- Sunspot information

### Glyph Radio

The script that started it all.

Internet radio with station presets and sleep timer support.

Still one of the most frequently used Glyph applications.

---

## Hardware

Glyph currently runs on:

- Raspberry Pi Zero 2 W
- 3.5" GPIO TFT Display
- MicroSD Card
- Portable USB Battery Pack
- Optional USB GPS Receiver
- Optional 4-port USB Hub

Other Raspberry Pi models should work with little or no modification.

---

## Installation

Documentation for individual modules will be provided in their respective directories.

Most modules require:

```bash
sudo apt update
sudo apt upgrade

sudo apt install \
    python3 \
    python3-pip \
    python3-pil \
    python3-requests \
    python3-serial \
    fbi
```

Some modules require additional dependencies.

Refer to module documentation.

---

## Project Status

Glyph is an active hobby project.

Many tools are experimental.

Some modules are polished enough for daily use, while others are still under development.

The project evolves based on real-world use and operator feedback.

---

## Why "Glyph"?

A glyph is a symbol that conveys information.

Glyph exists to do the same thing:

Turn information into something useful.

---

## License

MIT License

---

73,

**Caleb // W4XEN**
