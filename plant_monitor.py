"""
Pi Plant Monitor
================
Reads soil moisture (and optional light level) via an MCP3008 ADC
and sends the data to your meow meow scratch API.

Hardware:
  - MCP3008 ADC connected via SPI
  - Soil moisture sensor on channel 0
  - (Optional) Light sensor (LDR) on channel 1

Wiring (MCP3008 → Pi):
  VDD   → 3.3V
  VREF  → 3.3V
  AGND  → GND
  CLK   → SCLK (GPIO11)
  DOUT  → MISO (GPIO9)
  DIN   → MOSI (GPIO10)
  CS    → CE0  (GPIO8)
  DGND  → GND

Setup:
  sudo raspi-config  # enable SPI
  pip install -r requirements.txt
  export MEOW_API_KEY="your-key"
  python plant_monitor.py
"""

import os       # os.environ lets us read environment variables (like the API key)
import sys      # sys.exit() lets us stop the program with an error code
import time     # time.sleep() lets us pause between sensor readings
import spidev   # spidev lets Python talk to SPI devices (like our MCP3008 ADC chip)
# Meow sends data to the cloud; MeowError catches API failures. AuthError and
# RateLimitError are more specific kinds of MeowError, so we can tell you whether
# your key was rejected or you're just sending too fast.
from meow_sdk import Meow, MeowError, AuthError, RateLimitError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Read the API key from an environment variable (set with: export MEOW_API_KEY="your-key").
# We use an environment variable instead of hard-coding the key so it stays secret.
API_KEY = os.environ.get("MEOW_API_KEY")
if not API_KEY:
    print("Set MEOW_API_KEY environment variable")
    sys.exit(1)

APP = "pi-plant-monitor"    # Name of the app on meow meow scratch
ENDPOINT = "readings"       # Name of the collection endpoint that stores our data
INTERVAL = 60  # seconds between each sensor reading

# Raw ADC value above which we consider the soil "dry".
# Soil moisture sensors read HIGHER values when dry (counterintuitive!).
# 400 is a starting point — calibrate for your sensor by testing in wet and dry conditions.
# To calibrate: put sensor in dry air (note the number), put it in water (note the number),
# then pick a midpoint as your threshold.
DRY_THRESHOLD = 400  # raw ADC value — tune for your sensor

# ---------------------------------------------------------------------------
# Initialize the API client and SPI bus
# ---------------------------------------------------------------------------

# Create a Meow API client using your API key, used to send sensor data to the cloud
api = Meow(api_key=API_KEY)

# Create an SPI connection object — this represents the physical SPI interface on the Pi
spi = spidev.SpiDev()

# Open SPI bus 0, device 0.
# First 0 = SPI bus number (the Pi has one main SPI bus).
# Second 0 = CE0 (chip enable 0, GPIO8) to select the MCP3008.
# If you had a second SPI chip, you'd use spi.open(0, 1) and wire its CS to CE1.
spi.open(0, 0)

# SPI clock speed: 1.35 MHz (1,350,000 ticks per second).
# The MCP3008 supports up to 3.6 MHz at 5V, but at 3.3V it's safer to go slower.
# If you get noisy/wrong readings, try lowering this value (e.g., 500000).
spi.max_speed_hz = 1350000


def read_adc(channel):
    """Read a value (0–1023) from the MCP3008 on the given channel (0–7)."""

    # Build the 3-byte SPI command to send to the MCP3008:
    #
    # Byte 1: '1' = start bit. Tells the chip "a command is coming."
    #
    # Byte 2: '(8 + channel) << 4' selects which channel to read.
    #   - The '8' sets "single-ended mode" (read one channel, not the
    #     difference between two channels).
    #   - Adding 'channel' (0–7) picks which input to read.
    #   - '<< 4' is the LEFT SHIFT operator — it shifts all bits left by
    #     4 positions, which is the same as multiplying by 16. We do this
    #     because the MCP3008 expects these bits in a specific position.
    #   - Example for channel 0: (8+0) << 4 = 8 << 4 = 128 = 0b10000000
    #   - Example for channel 1: (8+1) << 4 = 9 << 4 = 144 = 0b10010000
    #
    # Byte 3: '0' = dummy byte. The chip needs extra clock cycles to finish
    #   its analog-to-digital conversion and send the result back, so we
    #   send a zero just to keep the clock running.
    cmd = [1, (8 + channel) << 4, 0]

    # Send the 3-byte command and receive 3 bytes back simultaneously.
    # SPI is "full-duplex" — it sends and receives at the same time.
    # reply[0] is meaningless (the chip hadn't started responding yet).
    # The actual 10-bit result is split across reply[1] and reply[2].
    reply = spi.xfer2(cmd)

    # Extract the 10-bit ADC result (a number from 0 to 1023):
    #
    # 'reply[1] & 3' — the '&' is a bitwise AND, also called "masking".
    #   3 in binary is 0b00000011. This keeps only the lowest 2 bits of
    #   byte 2 and throws away the upper 6 bits. These 2 bits are the
    #   "high part" of our 10-bit number (bits 8 and 9).
    #
    # '<< 8' — shift those 2 bits left by 8 positions, putting them into
    #   the 256s and 512s columns where they belong.
    #
    # '+ reply[2]' — add all 8 bits of byte 3. These are the "low part"
    #   of our 10-bit number (bits 0 through 7).
    #
    # Result: a single number from 0 (0V) to 1023 (3.3V reference voltage).
    value = ((reply[1] & 3) << 8) + reply[2]
    return value


def moisture_percent(raw):
    """Convert raw ADC value to a 0–100% moisture scale (inverted — wetter = lower raw)."""

    # Soil moisture sensors read LOWER when wet, HIGHER when dry (counterintuitive!).
    # This is because wet soil conducts electricity well, pulling the voltage down.
    #
    # Typical range for these sensors:
    #   ~300 = soaking wet
    #   ~700 = bone dry / in open air
    #
    # The formula (700 - raw) does two things:
    #   1. INVERTS the value: wet soil now gives a HIGH number (good, more intuitive)
    #   2. Maps the range: 700-300=400 raw units span the wet-to-dry range
    #
    # Dividing by 4 scales the ~400-unit range to roughly 0–100%.
    #   Wet:  (700 - 300) / 4 = 100%
    #   Dry:  (700 - 700) / 4 = 0%
    #
    # max(0, min(100, ...)) clamps the result so it never goes below 0 or above 100.
    #
    # CALIBRATION: These numbers (700 and 4) are starting points. Adjust them for YOUR
    # sensor — test in water and in air, note the raw values, and update accordingly.
    pct = max(0, min(100, (700 - raw) / 4))
    return round(pct, 1)


def main():
    print(f"Plant monitor running — reading every {INTERVAL}s")
    print("Press Ctrl+C to stop\n")

    while True:
        # Read the soil moisture sensor on MCP3008 channel 0
        raw_moisture = read_adc(0)

        # Convert the raw value to a human-friendly 0–100% scale
        pct = moisture_percent(raw_moisture)

        # Read the light sensor on MCP3008 channel 1
        # (If no light sensor is connected, this will read ~0 or ~1023)
        raw_light = read_adc(1)

        # Bundle all readings into a dictionary to send to the API
        data = {
            "moisture_raw": raw_moisture,       # Raw ADC value (0–1023)
            "moisture_percent": pct,            # Converted to 0–100% (inverted)
            "light_raw": raw_light,             # Raw light level (0–1023)
            "is_dry": raw_moisture > DRY_THRESHOLD,  # True if soil needs water
        }

        try:
            # Send the data to meow meow scratch via the API
            api.send(APP, ENDPOINT, data)

            # Print a human-readable summary to the terminal
            status = "DRY" if data["is_dry"] else "OK"
            print(f"Moisture: {pct}% (raw {raw_moisture}) | Light: {raw_light} | {status}")
        except AuthError as e:
            # A rejected key won't start working on the next reading, so stop
            # rather than filling the terminal with the same error all day.
            print(f"API key rejected: {e}")
            if e.hint:
                print(f"Hint: {e.hint}")
            sys.exit(1)
        except RateLimitError as e:
            # Sending faster than your plan allows — wait it out and continue.
            print(f"Rate limited: {e}")
            time.sleep(60)
        except MeowError as e:
            # Any other API failure (network issue, server problem), print the error
            # but keep running — we don't want a temporary glitch to kill the monitor
            print(f"Send failed: {e}")
            # .hint is a plain-English suggestion from the API, when it has one.
            if e.hint:
                print(f"Hint: {e.hint}")

        # Wait before the next reading. Default is 60 seconds.
        # Shorter intervals give more data but use more API calls.
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
