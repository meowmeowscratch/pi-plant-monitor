# Pi Plant Monitor

Keep your plants happy! This project checks how wet or dry your plant's soil is (and optionally how bright the room is) and sends the data to the internet. Watch moisture levels over time and know exactly when your plant needs water.

You'll build a system that reads your soil's moisture level every 60 seconds, converts it to a percentage, and sends it to [meow meow scratch](https://meowmeowscratch.com) so you can track it from anywhere. If you add a light sensor, you can monitor brightness too.

---

## What you'll learn

This is the most advanced project in the kit, and by the end you'll understand:

- **Analog vs. digital signals** -- Your Raspberry Pi's pins only understand HIGH (1) and LOW (0). That's digital. But soil moisture isn't just "wet" or "dry" -- it's a whole range of values. That's analog. You'll learn how to bridge that gap.
- **How an ADC (Analog-to-Digital Converter) works** -- The MCP3008 chip reads a smooth analog voltage and converts it to a number from 0 to 1023 that the Pi can understand.
- **SPI communication protocol** -- SPI is how the Pi and the MCP3008 talk to each other over 4 wires. You'll learn what each wire does and how data flows back and forth.
- **Reading multiple sensor channels** -- The MCP3008 has 8 input channels, so you can read up to 8 different sensors with one chip. We'll use channel 0 for moisture and channel 1 for light.
- **Calibrating sensor values for your specific hardware** -- Every sensor is slightly different. You'll learn how to test yours and adjust the code so the readings are accurate.
- **Bitshifting and bit masking** -- The chip communicates in individual bits. You'll learn what `<< 4` and `& 3` mean and why we need them.

---

## What you'll need

### Raspberry Pi with SPI enabled

Any Raspberry Pi with GPIO pins will work (Pi 3, Pi 4, Pi Zero W, etc.). SPI is a communication protocol built into the Pi, but it's turned off by default. You need to enable it before this project will work.

**How to enable SPI (step by step):**

1. Open a terminal on your Raspberry Pi (or SSH into it)
2. Type `sudo raspi-config` and press Enter
3. Use the arrow keys to go to **Interface Options** and press Enter
4. Select **SPI** and press Enter
5. Select **Yes** to enable SPI
6. Press Enter to confirm, then select **Finish**
7. Reboot your Pi: `sudo reboot`

After rebooting, you can verify SPI is enabled by running:

```bash
ls /dev/spidev*
```

You should see `/dev/spidev0.0` and `/dev/spidev0.1` listed. If nothing shows up, SPI isn't enabled yet -- try the steps above again.

### MCP3008 ADC chip

ADC stands for **Analog-to-Digital Converter**. Your Pi's GPIO pins only understand HIGH and LOW (1 and 0), but soil moisture is a range of values (analog). The MCP3008 reads an analog voltage and converts it to a number from 0 to 1023 that the Pi can understand.

It has **8 channels** (labeled CH0 through CH7), meaning it can read up to 8 different sensors at once. In this project we use CH0 for the moisture sensor and CH1 for the optional light sensor.

The MCP3008 communicates with the Pi using **SPI** (more on that below). It's a small 16-pin chip -- the notch or dot on top tells you which end is pin 1.

### Capacitive soil moisture sensor

This sensor has two metal pads that you push into the soil. Wet soil conducts electricity better than dry soil, so the sensor outputs a different voltage depending on moisture level. The sensor has three wires:

- **VCC** -- power (connect to 3.3V)
- **GND** -- ground
- **AOUT** -- analog output (the voltage that changes with moisture)

The AOUT wire connects to one of the MCP3008's input channels (CH0).

**Important quirk:** These sensors read **LOWER** values when wet and **HIGHER** values when dry. That's counterintuitive! The code handles this by inverting the values so that 100% = wet and 0% = dry.

### Optional: LDR (Light Dependent Resistor) + 10K resistor

An LDR changes its resistance based on light -- bright light = low resistance, darkness = high resistance. By itself, the Pi can't read resistance directly. But if you combine the LDR with a fixed 10K resistor in a "voltage divider" circuit, you get a voltage that varies with brightness. That voltage goes into MCP3008 channel 1.

You don't need this for basic plant monitoring, but it's a nice extra if you want to track how much light your plant gets.

### Breadboard and jumper wires

A breadboard lets you connect components without soldering. Jumper wires plug into the breadboard and connect everything together. You'll need a mix of male-to-male and male-to-female jumper wires (male-to-female to connect from the breadboard to the Pi's GPIO pins).

---

## Understanding SPI (Serial Peripheral Interface)

Before we wire things up, let's understand how the Pi talks to the MCP3008. They communicate using **SPI**, which uses 4 wires:

| Wire | Full name         | What it does                                                            | Pi GPIO pin        |
|------|-------------------|-------------------------------------------------------------------------|---------------------|
| CLK  | Clock             | A timing signal -- like a metronome that keeps both devices in sync     | GPIO11 (pin 23)     |
| MOSI | Master Out Slave In | Sends data **from** the Pi **to** the MCP3008                        | GPIO10 (pin 19)     |
| MISO | Master In Slave Out | Sends data **from** the MCP3008 **to** the Pi                        | GPIO9 (pin 21)      |
| CS   | Chip Select       | Tells the MCP3008 "I'm talking to you" (pulled LOW to activate)         | GPIO8/CE0 (pin 24)  |

Think of it like a phone call: CS is picking up the phone, CLK is the rhythm of the conversation, MOSI is the Pi talking, and MISO is the chip talking back. SPI is "full-duplex," meaning both sides can talk at the same time (like a phone, not a walkie-talkie).

The Pi is the "master" (it controls the clock and decides when to communicate) and the MCP3008 is the "slave" (it responds when asked).

---

## Wiring diagram

Here's how to connect the MCP3008 chip. The chip has a small notch (or dot) on one end -- that marks the side where pin 1 (CH0) is. Place the chip across the center gap of your breadboard so each side's pins are on separate rows.

```
                          MCP3008
                        +---v---+
     Moisture sensor ---| CH0  VDD |--- 3.3V
     Light sensor    ---| CH1 VREF |--- 3.3V
                    nc -| CH2 AGND |--- GND
                    nc -| CH3  CLK |--- SCLK (GPIO11, pin 23)
                    nc -| CH4 DOUT |--- MISO (GPIO9, pin 21)
                    nc -| CH5  DIN |--- MOSI (GPIO10, pin 19)
                    nc -| CH6   CS |--- CE0  (GPIO8, pin 24)
                    nc -| CH7 DGND |--- GND
                        +--------+

     ("nc" = not connected -- these channels are unused)
     ("v" = the notch on the chip, used to orient it correctly)

     Soil Moisture Sensor:
       VCC  -> 3.3V
       GND  -> GND
       AOUT -> MCP3008 CH0

     Light Sensor (optional):
       One leg of LDR  -> 3.3V
       Other leg of LDR -> MCP3008 CH1 AND one leg of 10K resistor
       Other leg of 10K resistor -> GND
```

### Full wiring reference table

| MCP3008 Pin | Pin # | Connects to              | Why                                                      |
|-------------|-------|--------------------------|----------------------------------------------------------|
| CH0         | 1     | Soil moisture sensor AOUT | Analog input from moisture sensor                       |
| CH1         | 2     | LDR voltage divider      | Analog input from light sensor (optional)                |
| CH2         | 3     | (not connected)          | Unused channel                                           |
| CH3         | 4     | (not connected)          | Unused channel                                           |
| CH4         | 5     | (not connected)          | Unused channel                                           |
| CH5         | 6     | (not connected)          | Unused channel                                           |
| CH6         | 7     | (not connected)          | Unused channel                                           |
| CH7         | 8     | (not connected)          | Unused channel                                           |
| DGND        | 9     | GND                      | Digital ground -- connects chip's digital side to ground |
| CS          | 10    | GPIO8 / CE0 (pin 24)    | Chip Select -- Pi pulls this LOW to talk to the chip     |
| DIN         | 11    | GPIO10 / MOSI (pin 19)  | Data In -- Pi sends commands to the chip on this wire    |
| DOUT        | 12    | GPIO9 / MISO (pin 21)   | Data Out -- chip sends readings back to the Pi           |
| CLK         | 13    | GPIO11 / SCLK (pin 23)  | Clock -- timing signal so Pi and chip stay in sync       |
| AGND        | 14    | GND                      | Analog ground -- connects chip's analog side to ground   |
| VREF        | 15    | 3.3V                     | Reference voltage -- the max voltage the chip measures   |
| VDD         | 16    | 3.3V                     | Power supply for the chip                                |

**Double-check your wiring before powering on!** The most common problems come from wires in the wrong place.

---

## Step-by-step setup

### Step 1: Enable SPI on your Raspberry Pi

If you haven't already, follow the instructions in the "Raspberry Pi with SPI enabled" section above. This only needs to be done once.

### Step 2: Wire up the circuit

Follow the wiring diagram above. Take your time and double-check each connection.

### Step 3: Install the required Python packages

Open a terminal on your Pi and navigate to this project folder. Then install the dependencies:

```bash
pip install -r requirements.txt
```

**What is `pip`?** `pip` is Python's package manager -- it downloads and installs libraries (pre-written code) that other people have made. Think of it like an app store for Python code. The `-r requirements.txt` flag tells pip to install everything listed in the `requirements.txt` file.

This command installs two libraries:

- **`spidev`** -- lets Python talk to SPI devices. Without this, Python has no way to communicate with the MCP3008 chip. It provides functions like `spi.open()` and `spi.xfer2()` that handle all the low-level SPI communication.
- **`meow-sdk`** -- the meow meow scratch SDK that sends your sensor data to the cloud so you can view it online.

### Step 4: Set your API key

You need an API key so the script can send data to meow meow scratch. Set it as an environment variable:

```bash
export MEOW_API_KEY="your-key-here"
```

**What is an environment variable?** It's a value stored in your terminal session that programs can read. We use it for the API key instead of putting it directly in the code, so you don't accidentally share your secret key if you share your code. The `export` command makes it available to any program you run from that terminal.

**Note:** This only lasts for your current terminal session. If you close the terminal and open a new one, you'll need to run the `export` command again. To make it permanent, add the line to your `~/.bashrc` file.

### Step 5: Run the script

```bash
python plant_monitor.py
```

The script will read your sensors every 60 seconds, print the values to the terminal, and send them to the cloud. Press `Ctrl+C` to stop it.

---

## How the code works

This is the most important section. Let's walk through what the code is actually doing, in plain English.

### Setting up SPI

```python
spi = spidev.SpiDev()    # Create an SPI connection object
spi.open(0, 0)           # Open SPI bus 0, device 0
spi.max_speed_hz = 1350000  # Set clock speed to 1.35 MHz
```

`spi.open(0, 0)` -- The first `0` is the SPI bus number (the Pi has one main SPI bus). The second `0` selects CE0 (chip enable 0, which is GPIO8) to identify the MCP3008. If you had a second SPI chip, you'd use `spi.open(0, 1)` and wire its CS pin to CE1.

`spi.max_speed_hz = 1350000` -- This sets the clock speed to 1.35 MHz (1,350,000 ticks per second). The MCP3008 supports up to 3.6 MHz at 5V, but we're running it at 3.3V so it's safer to go slower. If you get weird readings, try lowering this number.

### Reading a sensor value: the SPI command

```python
def read_adc(channel):
    cmd = [1, (8 + channel) << 4, 0]
    reply = spi.xfer2(cmd)
    value = ((reply[1] & 3) << 8) + reply[2]
    return value
```

This is the core of the project. Let's break down each line.

#### Building the command: `cmd = [1, (8 + channel) << 4, 0]`

To read from the MCP3008, we send **3 bytes** (a byte is a number from 0 to 255). Each byte has a job:

- **Byte 1: `1`** -- This is the **start bit**. It tells the MCP3008 "a command is coming."
- **Byte 2: `(8 + channel) << 4`** -- This tells the chip **which channel to read**. Let's unpack this:
  - The `8` sets "single-ended mode" (read one channel by itself, as opposed to comparing two channels).
  - Adding `channel` (0-7) selects which of the 8 inputs to read.
  - `<< 4` is the **left shift** operator. It shifts all the bits left by 4 positions. In practical terms, this is the same as multiplying by 16. We need to do this because the MCP3008 expects the channel selection bits to be in a specific position within the byte.
  - **Example for channel 0:** `(8 + 0) << 4` = `8 << 4` = `128` = `0b10000000` in binary.
  - **Example for channel 1:** `(8 + 1) << 4` = `9 << 4` = `144` = `0b10010000` in binary.
- **Byte 3: `0`** -- This is just a **placeholder** (dummy byte). The chip needs extra clock cycles to finish its conversion and send the result back, so we send a zero to keep the clock running.

#### Sending and receiving: `reply = spi.xfer2(cmd)`

`xfer2` sends our 3-byte command and **simultaneously receives 3 bytes back**. SPI is full-duplex -- it sends and receives at the same time. The first byte of the reply is meaningless (the chip hadn't started responding yet). The actual data is in bytes 2 and 3.

#### Extracting the result: `((reply[1] & 3) << 8) + reply[2]`

The MCP3008 returns a **10-bit value** (a number from 0 to 1023), but it's split across two bytes. Here's how we piece it together:

- `reply[1] & 3` -- The `&` is a **bitwise AND** (also called "masking"). `3` in binary is `0b00000011`. This operation keeps only the **lowest 2 bits** of byte 2 and throws away the rest. These 2 bits are the "high" part of our 10-bit number (bits 8 and 9).
- `<< 8` -- Shift those 2 bits left by 8 positions, putting them in the correct place (the 256s and 512s columns).
- `+ reply[2]` -- Add all 8 bits of byte 3. These are the "low" part of our 10-bit number (bits 0 through 7).
- **Result:** A single number from 0 to 1023 representing the voltage on that channel. 0 means 0V, 1023 means 3.3V (our reference voltage).

**If you're confused by the bit stuff:** That's totally normal. The key takeaway is that `read_adc(0)` gives you a number from 0 to 1023 representing how much voltage the moisture sensor is outputting. You don't need to fully understand the bit manipulation to use this project.

### Converting to moisture percentage: the inversion

```python
def moisture_percent(raw):
    pct = max(0, min(100, (700 - raw) / 4))
    return round(pct, 1)
```

Soil moisture sensors read **LOWER** values when wet and **HIGHER** values when dry. That's counterintuitive! Here's why: wet soil conducts electricity well, which pulls the sensor's output voltage down.

Typical readings:
- **Soaking wet soil:** ~300 (low raw value)
- **Bone dry soil / air:** ~700 (high raw value)

The formula `(700 - raw) / 4` does two things:
1. **Inverts the value:** `700 - raw` makes it so wet soil gives a HIGH number and dry soil gives a LOW number (much more intuitive).
2. **Scales to roughly 0-100%:** The range is about 400 units (700 - 300 = 400), so dividing by 4 maps it to approximately 0-100.

`max(0, min(100, ...))` clamps the result so it never goes below 0% or above 100%.

### The dry threshold

```python
DRY_THRESHOLD = 400  # raw ADC value — tune for your sensor
```

If the raw moisture reading is above 400, the code considers the soil "dry." This value of 400 is a starting point -- your sensor may be different.

### Calibration: adjusting for YOUR sensor

Every sensor is slightly different. To calibrate yours:

1. **Measure "dry":** Hold the sensor in open air (completely dry). Run the script and note the raw value. This might be around 650-750.
2. **Measure "wet":** Put the sensor in a glass of water (not past the electronics line!). Note the raw value. This might be around 250-350.
3. **Adjust the code:**
   - Change `DRY_THRESHOLD` to roughly the midpoint between your wet and dry values.
   - In `moisture_percent()`, change `700` to your dry-air reading.
   - Change `4` to `(your_dry_value - your_wet_value) / 100` so the scale maps properly to 0-100%.

**Example:** If your sensor reads 320 in water and 680 in air:
- Set `DRY_THRESHOLD = 500` (midpoint)
- Change `(700 - raw) / 4` to `(680 - raw) / 3.6` (because 680 - 320 = 360, and 360 / 100 = 3.6)

### The main loop

The `main()` function runs forever in a loop:

1. Read the moisture sensor (channel 0)
2. Convert the raw value to a percentage
3. Read the light sensor (channel 1)
4. Bundle all the data into a dictionary
5. Send it to meow meow scratch via the API
6. Print the values to the terminal
7. Wait 60 seconds
8. Repeat

---

## Troubleshooting

### All readings are 0

**SPI is probably not enabled.** Run `ls /dev/spidev*` in a terminal. If nothing shows up, go back to the "Enable SPI" section and follow those steps. Don't forget to reboot after enabling SPI.

### All readings are 1023

**The sensor is probably disconnected from the MCP3008.** When a channel has nothing connected, it "floats" to the maximum value. Check that your moisture sensor's AOUT wire is securely connected to MCP3008 CH0.

### Readings seem backwards (high when wet, low when dry)

**That's actually normal for the raw values!** The code inverts them in the `moisture_percent()` function. If the printed percentage still seems backwards, double-check that the inversion formula is correct. The raw values should go DOWN when the sensor is in water.

### Readings are jumping around wildly

- Make sure your wiring is solid -- loose connections cause noisy readings.
- Try lowering `spi.max_speed_hz` (e.g., to `500000`).
- Add a small capacitor (0.1uF) between the sensor's AOUT and GND to smooth the signal.

### `ModuleNotFoundError: No module named 'spidev'`

Run `pip install spidev` to install the SPI library. If you're using Python 3 and `pip` doesn't work, try `pip3 install spidev`.

### `FileNotFoundError: [Errno 2] No such file or directory: '/dev/spidev0.0'`

SPI is not enabled. See "All readings are 0" above.

### `Set MEOW_API_KEY environment variable` and the script exits

You forgot to set the API key. Run:

```bash
export MEOW_API_KEY="your-key-here"
```

Then run the script again. Replace `your-key-here` with your actual key from meow meow scratch.

### Readings don't match expected moisture levels

You need to calibrate. See the "Calibration" section above. Every sensor behaves slightly differently.

---

## API setup

To send data to meow meow scratch, you need to create an app and endpoint:

1. Go to [meowmeowscratch.com](https://meowmeowscratch.com) and log in (or create an account)
2. Create a new app called **`pi-plant-monitor`**
3. Add a collection endpoint called **`readings`**
4. Add these fields to the endpoint:

| Field name         | Type    | Description                                 |
|--------------------|---------|---------------------------------------------|
| `moisture_raw`     | number  | The raw ADC value (0-1023) from the sensor  |
| `moisture_percent` | number  | Moisture converted to 0-100% scale          |
| `light_raw`        | number  | Raw ADC value from the light sensor         |
| `is_dry`           | boolean | `true` if soil is dry, `false` if moist     |

5. Copy your API key from the dashboard
6. Set it in your terminal: `export MEOW_API_KEY="your-key-here"`
7. Run the script and check the dashboard to see your data coming in!

Once data is flowing, you can use meow meow scratch to build charts, set up alerts (e.g., "notify me when my plant is dry"), and track moisture trends over time.
