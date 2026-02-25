# Pi Plant Monitor

Monitor your plant's soil moisture (and ambient light) using an MCP3008 ADC and send the data to [meow meow scratch](https://meowmeowscratch.com).

## Hardware

- Raspberry Pi with SPI enabled (`sudo raspi-config`)
- MCP3008 ADC
- Capacitive soil moisture sensor (channel 0)
- Optional: LDR light sensor (channel 1)

## Setup

```bash
pip install -r requirements.txt
export MEOW_API_KEY="your-key"
python plant_monitor.py
```

Reads every 60 seconds. Tune `DRY_THRESHOLD` in the script for your sensor.

## API setup

Create an app called `pi-plant-monitor` with a collection endpoint `readings` and fields: `moisture_raw` (number), `moisture_percent` (number), `light_raw` (number), `is_dry` (boolean).
