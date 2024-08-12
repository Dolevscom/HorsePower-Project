import serial
import time

# Replace with your actual port and baud rate
serial_port = '/dev/cu.usbserial-AR0JYRZK'  # Update to match your system
baud_rate = 115200  # This should match the baud rate set in your Arduino code

try:
    # Initialize the serial connection
    arduino_serial = serial.Serial(serial_port, baud_rate, timeout=1)
    print(f"Connected to {serial_port} at {baud_rate} baud.")
    
    # Give some time for the connection to settle
    time.sleep(2)
    
    while True:
        # Read the data from the Arduino
        arduino_data = arduino_serial.readline().decode('utf-8').strip()
        
        if arduino_data:
            # Just print the raw data
            print(f"Distance Data: {arduino_data}")
        
except serial.SerialException:
    print(f"Could not connect to {serial_port}. Please check the connection.")
except KeyboardInterrupt:
    print("Exiting...")
finally:
    if 'arduino_serial' in locals():
        arduino_serial.close()
        print("Serial connection closed.")
