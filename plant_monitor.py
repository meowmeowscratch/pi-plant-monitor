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

import os
import sys
import time
import spidev
from meow_sdk import Meow, MeowError

API_KEY = os.environ.get("MEOW_API_KEY")
if not API_KEY:
    print("Set MEOW_API_KEY environment variable")
    sys.exit(1)

APP = "pi-plant-monitor"
ENDPOINT = "readings"
INTERVAL = 60  # seconds
DRY_THRESHOLD = 400  # raw ADC value — tune for your sensor

api = Meow(api_key=API_KEY)

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000


def read_adc(channel):
    """Read a value (0–1023) from the MCP3008 on the given channel (0–7)."""
    cmd = [1, (8 + channel) << 4, 0]
    reply = spi.xfer2(cmd)
    value = ((reply[1] & 3) << 8) + reply[2]
    return value


def moisture_percent(raw):
    """Convert raw ADC value to a 0–100% moisture scale (inverted — wetter = lower raw)."""
    # Typical range: ~300 (wet) to ~700 (dry). Adjust for your sensor.
    pct = max(0, min(100, (700 - raw) / 4))
    return round(pct, 1)


def main():
    print(f"Plant monitor running — reading every {INTERVAL}s")
    print("Press Ctrl+C to stop\n")

    while True:
        raw_moisture = read_adc(0)
        pct = moisture_percent(raw_moisture)
        raw_light = read_adc(1)

        data = {
            "moisture_raw": raw_moisture,
            "moisture_percent": pct,
            "light_raw": raw_light,
            "is_dry": raw_moisture > DRY_THRESHOLD,
        }

        try:
            api.send(APP, ENDPOINT, data)
            status = "DRY" if data["is_dry"] else "OK"
            print(f"Moisture: {pct}% (raw {raw_moisture}) | Light: {raw_light} | {status}")
        except MeowError as e:
            print(f"Send failed: {e}")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
