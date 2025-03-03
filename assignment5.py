import time
import datetime
from gpiozero import LED, Button
from socket import *
import matplotlib.pyplot as plt
from itertools import cycle
import spidev
import socketio
# Constants
MYPORT = 2910
BROADCAST_IP = '255.255.255.255'

sio = socketio.Client()

# Connect to the Node.js server
sio.connect('http://localhost:3000')

SPI_BUS = 0       # SPI bus (0 or 1)
SPI_DEVICE = 0    # SPI device (CE0 = 0, CE1 = 1)
spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEVICE)

# Set SPI speed and mode
spi.max_speed_hz = 8000000  # 8 MHz
spi.mode = 0  # SPI mode 0 (CPOL=0, CPHA=0)

# MAX7219 Registers
MAX7219_REG_NOOP = 0x00  # No Operation
MAX7219_REG_DIGIT0 = 0x01  # Digit 0 register
MAX7219_REG_DIGIT1 = 0x02  # Digit 1 register
MAX7219_REG_DIGIT2 = 0x03  # Digit 2 register
MAX7219_REG_DIGIT3 = 0x04  # Digit 3 register
MAX7219_REG_DIGIT4 = 0x05  # Digit 4 register
MAX7219_REG_DIGIT5 = 0x06  # Digit 5 register
MAX7219_REG_DIGIT6 = 0x07  # Digit 6 register
MAX7219_REG_DIGIT7 = 0x08  # Digit 7 register
MAX7219_REG_DECODEMODE = 0x09  # Decode mode register
MAX7219_REG_INTENSITY = 0x0A  # Intensity register (brightness)
MAX7219_REG_SCANLIMIT = 0x0B  # Scan limit register (number of rows)
MAX7219_REG_SHUTDOWN = 0x0C  # Shutdown register (turn on/off)
MAX7219_REG_DISPLAYTEST = 0x0F  # Display test register (test pattern)
NUM_ROWS = 8
NUM_COLS = 8

selected_col = 0

# Matrix to hold the LED states
led_matrix = [[0] * NUM_COLS for _ in range(NUM_ROWS)]

# LEDs and Buttons
led_pins = [23, 24, 25]  # GPIO pins for LEDs
available_leds = cycle([LED(pin) for pin in led_pins])  # Cycle through LEDs
master_led_map = {}  # Dynamic mapping of master IPs to LEDs
white_led = LED(17)
button = Button(4)

photocell_to_send=[]

# Master State
current_master = None
master_start_time = None
master_time = {}  # Tracks time spent for each master

# Photocell Data
photocell_data = []
photocell_time = []


def get_led_for_master(master_ip):
    """Assign an LED to a master dynamically."""
    if master_ip not in master_led_map:
        master_led_map[master_ip] = next(available_leds)
    return master_led_map[master_ip]


def reset_all_esp8266():
    """Send a reset packet to all ESP8266 devices."""
    print("Sending RESET_SWARM_PACKET to all ESP8266 devices.")
    s = socket(AF_INET, SOCK_DGRAM)
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    reset_command = bytearray([0xFF, 0xFF, 0x00, 0x00])
    s.sendto(reset_command, (BROADCAST_IP, MYPORT))
    print(f"Reset command sent to {BROADCAST_IP}:{MYPORT}")


def on_button_pressed():
    """Handle button press to reset devices, toggle LED, and start a new log file."""
    print("Button pressed")
    reset_all_esp8266()
    white_led.on()
    time.sleep(3)
    white_led.off()
    # start_new_log_file()

    global photocell_data, photocell_time, photocell_to_send, master_time, bars
    
    # Clear previous data
    photocell_data = []          # Full data reset
    photocell_time = []          # Time history reset
    photocell_to_send = []       # Data to send reset
    master_time = {}             # Reset master time
    
    sio.emit('resetCharts')

button.when_pressed = on_button_pressed

def process_photocell_data(ip, photocell_value):
    """Process and update photocell data for the graph."""
    global photocell_data, photocell_time, photocell_to_send

    current_time = time.time()
    
    # Append to both lists
    photocell_data.append(photocell_value)  # Full history
    photocell_time.append(current_time)     # Full history
    photocell_to_send.append({'ip': ip, 'photocell_value': photocell_value})  # Latest data to send

    # Update LED matrix
    update_matrix()

def processCommand(s, address, message):
    """Process incoming commands and update LED status."""
    global current_master, master_start_time, master_time, photocell_to_send

    ip = address[0]
    led = get_led_for_master(ip)

    print(f"Processing message from: {ip}")

    # Blink LED for the IP
    led.on()
    time.sleep(0.3)
    led.off()

    # Ensure IP is added to the master_time dictionary if not already
    if ip not in master_time:
        master_time[ip] = 0

    # Extract photocell value and update graphs
    if len(message) == 4 and message[0] == 0x01 and message[3] == 0xFF:
        photocell_value = (message[1] << 8) | message[2]
        print(f"Extracted photocell value: {photocell_value}")
        process_photocell_data(ip, photocell_value)

        # Update current master time only if the current master has changed
        if current_master != ip:
            if current_master is not None:
                elapsed_time = time.time() - master_start_time
                if current_master not in master_time:
                    master_time[current_master] = 0
                master_time[current_master] += elapsed_time
            current_master = ip
            master_start_time = time.time()

    # Emit only the most recent data
    sio.emit('updatePhotocellData', {
        'photocellData': photocell_to_send,  # Send only the latest data
        'masterData': master_time
    })

# UDP Server
def listen_for_commands():
    """Set up the UDP server to listen for incoming commands."""
    s = socket(AF_INET, SOCK_DGRAM)
    s.bind(('', MYPORT))
    s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

    while True:
        message, address = s.recvfrom(1024)
        processCommand(s, address, message)


def init_max7219():
    """Initialize the MAX7219 LED matrix."""
    # Wake up from shutdown mode
    spi.xfer2([MAX7219_REG_SHUTDOWN, 0x01])  # 0x01 = Normal operation
    # Set scan limit to 7 (all rows enabled)
    spi.xfer2([MAX7219_REG_SCANLIMIT, 0x07])  
    # Disable BCD decode mode (matrix mode)
    spi.xfer2([MAX7219_REG_DECODEMODE, 0x00])  
    # Set intensity (brightness)
    spi.xfer2([MAX7219_REG_INTENSITY, 0x08])  # Medium brightness
    # Exit test mode
    spi.xfer2([MAX7219_REG_DISPLAYTEST, 0x00])  
    # Clear display
    clear_matrix()

def update_matrix(max_row=8, max_data=1024):
    global photocell_data, selected_col

    # Calculate the average of the last four photocell readings
    last_4_values = photocell_data[-4:]
    data = sum(last_4_values) // len(last_4_values)

    selected_col = (selected_col + 1) % max_row
    fraction_VALUE = max_data // max_row
    
    # Initialize the row data to 0 (all LEDs off initially)
    row_data = 0

    print("Fraction VALUE:", fraction_VALUE)

    # Loop over each row and set the appropriate LEDs
    for row in range(max_row):
        if data > (row * fraction_VALUE):  # Check if the data is above the threshold for this row
            row_data |= (1 << row)  # Turn on the LED at the current row
            print(f"LED on row {row} is ON.")
        else:
            row_data &= ~(1 << row)  # Turn off the LED at the current row
            print(f"LED on row {row} is OFF.")

    # Pass the entire row_data to set_row to update the LEDs in the selected column
    set_row(selected_col, row_data)


def set_row(row, value):
    print(row, value)
    """Set a specific row on the LED matrix."""
    if row < 0 or row >= NUM_ROWS:
        raise ValueError("Row must be between 0 and 7")
    
    # Debug output
    print(f"Setting row {row} with value {bin(value)}")
    
    spi.xfer2([MAX7219_REG_DIGIT0 + row, value & 0xFF])  # Send row data

def clear_matrix():
    for row in range(8):
        set_row(row, 0)

if __name__ == "__main__":
    try:
        init_max7219()  # Initialize the MAX7219
        while True:
            listen_for_commands()
            time.sleep(4)  # Update every 4 seconds
    except KeyboardInterrupt:
        clear_matrix()  # Clear the display when interrupted
        spi.close()  # Close SPI connection
        print("Program exited")