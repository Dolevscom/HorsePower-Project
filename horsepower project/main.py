import serial
import matplotlib.pyplot as plt
import numpy as np
from image_blender import blend_images  # Import the image blending function
import matplotlib.animation as animation 

# Set up the serial connection with the arduino
serial_connection = serial.Serial('/dev/cu.usbserial-AR0JYRZK', 9600)  # Replace with your actual port

# Function to calculate horsepower from speed
def calculate_horsepower(speed_mps, weight=70):
    return (weight * speed_mps) / 745.7

# Function to apply a low-pass filter
def low_pass_filter(value, previous_value, alpha=0.1):
    return alpha * value + (1 - alpha) * previous_value

# Infinite data generator that reads data from the serial port
def infinite_data_generator(serial_connection, speed_threshold=0.05, window_size=5):
    last_filtered_speed = 0.0  # Initialize for low-pass filter
    
    while True:
        try:
            # Read line from the serial port
            line = serial_connection.readline().decode('utf-8').strip()
            print(f"Raw data from serial: {line}")  # Debug: print raw data
            
            # Convert speed to a positive value (eliminate negative readings)
            speed_mps = abs(float(line))
            
            # Apply a threshold to ignore small speeds caused by noise
            if abs(speed_mps) < speed_threshold:
                speed_mps = 0.0
            
            # Apply a low-pass filter
            filtered_speed = low_pass_filter(speed_mps, last_filtered_speed)
            last_filtered_speed = filtered_speed  # Update for next iteration
            
            # Calculate horsepower and normalize to absolute values
            hp = abs(calculate_horsepower(filtered_speed))
            yield hp
            
        except ValueError:
            # Handle any issues with data conversion
            continue



# Initialize your data generator
hp_data_generator = infinite_data_generator(serial_connection)

# Create your figure for displaying the image
fig, ax = plt.subplots()
ax.axis('off')  # Hide axes

min_hp_observed = float('inf')
max_hp_observed = float('-inf')

min_hp_observed = float('inf')
max_hp_observed = float('-inf')

def update(frame):
    global min_hp_observed, max_hp_observed
    
    hp = next(hp_data_generator)  # Fetch new data from the generator
    
    # Update observed min and max horsepower values
    if hp < min_hp_observed:
        min_hp_observed = hp
    if hp > max_hp_observed:
        max_hp_observed = hp
    
    # Avoid zero division by ensuring min_hp and max_hp are not the same
    if min_hp_observed == max_hp_observed:
        # Default to the mid-blend image if no variation in HP is observed
        result_img = blend_images(hp, min_hp=0, max_hp=1)  # Adjust with a small range
    else:
        result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
    
    ax.imshow(result_img)  # Display the blended image
    plt.draw()


# Set up your animation to update only the image
ani = animation.FuncAnimation(fig, update, frames=np.arange(0, 1000), blit=False, interval=100)

plt.show()
