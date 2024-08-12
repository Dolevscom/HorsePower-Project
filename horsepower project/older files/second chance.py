# import serial
# import time

# # Replace with your actual port and baud rate
# serial_port = '/dev/cu.usbserial-AR0JYRZK'  # Update to match your system
# baud_rate = 115200  # This should match the baud rate set in your Arduino code

# try:
#     # Initialize the serial connection
#     arduino_serial = serial.Serial(serial_port, baud_rate, timeout=1)
#     print(f"Connected to {serial_port} at {baud_rate} baud.")
    
#     # Give some time for the connection to settle
#     time.sleep(2)
    
#     while True:
#         # Read the data from the Arduino
#         arduino_data = arduino_serial.readline().decode('utf-8').strip()
        
#         if arduino_data:
#             # Just print the raw data
#             print(f"Distance Data: {arduino_data}")
        
# except serial.SerialException:
#     print(f"Could not connect to {serial_port}. Please check the connection.")
# except KeyboardInterrupt:
#     print("Exiting...")
# finally:
#     if 'arduino_serial' in locals():
#         arduino_serial.close()
#         print("Serial connection closed.")


####################################################################################################            

import serial
import matplotlib.pyplot as plt
import numpy as np
from image_blender import blend_images  # Assuming you have this function
import matplotlib.animation as animation
import time

# Set up the serial connection with the Arduino
serial_connection = serial.Serial('/dev/cu.usbserial-AR0JYRZK', 115200)  # Replace with your actual port

# # Function to calculate horsepower from speed
# def calculate_horsepower(speed_mps, weight=70):
#     return (weight * speed_mps) / 745.7

# # Function to apply a low-pass filter
# def low_pass_filter(value, previous_value, alpha=0.1):
#     return alpha * value + (1 - alpha) * previous_value

# # Infinite data generator that reads range data from the serial port
# def infinite_data_generator(serial_connection, speed_threshold=0.05, window_size=5):
#     last_distance = None  # Initialize for distance tracking
#     last_time = time.time()  # Get the current time
#     last_filtered_speed = 0.0  # Initialize for low-pass filter

#     while True:
#         try:
#             # Read line from the serial port
#             line = serial_connection.readline().decode('utf-8').strip()
#             print(f"Raw data from serial: {line}")  # Debug: print raw data
            
#             # Parse the range (distance) data
#             current_distance = float(line)
#             current_time = time.time()
            
#             # Calculate the time difference
#             time_diff = current_time - last_time if last_time else 1
            
#             if last_distance is not None:
#                 # Calculate speed (m/s) based on the change in distance
#                 speed_mps = abs(current_distance - last_distance) / time_diff
                
#                 # Apply a threshold to ignore small speeds caused by noise
#                 if abs(speed_mps) < speed_threshold:
#                     speed_mps = 0.0
                
#                 # Apply a low-pass filter
#                 filtered_speed = low_pass_filter(speed_mps, last_filtered_speed)
#                 last_filtered_speed = filtered_speed  # Update for next iteration

#                 # Calculate horsepower and normalize to absolute values
#                 hp = abs(calculate_horsepower(filtered_speed))
#                 yield hp
            
#             # Update last distance and time
#             last_distance = current_distance
#             last_time = current_time
            
#         except ValueError:
#             # Handle any issues with data conversion
#             continue

import serial
import time

# Set up the serial connection with the Arduino
serial_connection = serial.Serial('/dev/cu.usbserial-AR0JYRZK', 115200)  # Replace with your actual port

# Infinite data generator that reads range data from the serial port
def infinite_data_generator(serial_connection):
    while True:
        try:
            # Read line from the serial port
            line = serial_connection.readline().decode('utf-8').strip()
            
            # Get the current time
            current_time = time.time()
            
            # Parse the range (distance) data
            current_distance = float(line)
            
            # Output the raw data and timestamp
            print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}, Data: {current_distance}")
            
        except ValueError:
            # Handle any issues with data conversion
            continue

# Run the data generator
infinite_data_generator(serial_connection)






# Initialize your data generator
# hp_data_generator = infinite_data_generator(serial_connection)

# # Create your figure for displaying the image
# fig, ax = plt.subplots()
# ax.axis('off')  # Hide axes

# min_hp_observed = float('inf')
# max_hp_observed = float('-inf')
# first_frame = True  # Flag to check if it's the first frame

# def update(frame):
#     global min_hp_observed, max_hp_observed, first_frame
    
#     if first_frame:
#         # Start with an empty frame
#         ax.imshow(np.zeros((100, 100, 3)))  # Display an empty black image or adjust size as needed
#         first_frame = False
#     else:
#         hp = next(hp_data_generator)  # Fetch new data from the generator
        
#         # Update observed min and max horsepower values
#         if hp < min_hp_observed:
#             min_hp_observed = hp
#         if hp > max_hp_observed:
#             max_hp_observed = hp
        
#         # Avoid zero division by ensuring min_hp and max_hp are not the same
#         if min_hp_observed == max_hp_observed:
#             # Default to the mid-blend image if no variation in HP is observed
#             result_img = blend_images(hp, min_hp=0, max_hp=1)  # Adjust with a small range
#         else:
#             result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
        
#         ax.imshow(result_img)  # Display the blended image
#         plt.draw()

# # Set up your animation to update only the image
# ani = animation.FuncAnimation(fig, update, frames=np.arange(0, 1000), blit=False, interval=100)

# plt.show()
