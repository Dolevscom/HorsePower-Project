import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from PIL import Image, ImageDraw
import numpy as np

###### CONSTANTS ######
CURRENT_WEIGHT = 1.23  # Weight of the object in kg  
MIN_HP = 0
MAX_HP = 100
DISTANCE_CHANGE_THRESHOLD = 30
last_hp = 0  # Global variable to store the last horsepower value
is_try_active = False  # To track if a "try" is ongoing
highest_hp_in_try = 0  # To store the highest horsepower during a "try"
last_try_max_hp = 0  # To store the max horsepower of the last try

##### GLOBALS ######

# Set up the serial connection with the Arduino
serial_connection = serial.Serial('/dev/cu.usbserial-AR0JYRZK', 115200)  # Replace with your actual port

# Load the images
empty_image_path = '/Users/dolevsmac/Desktop/SciMuse project/horsepower project/watt portait/empty.png'
full_image_path = '/Users/dolevsmac/Desktop/SciMuse project/horsepower project/watt portait/full.png'
empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")
# Ensure the images are the same size
empty_img = empty_img.resize(full_img.size)

###### HELPER FUNCTIONS ######

# Function to calculate horsepower from speed
def calculate_horsepower(speed_mps):
    return (CURRENT_WEIGHT * speed_mps) / 745.7

# Function to blend images based on horsepower value
def blend_images(horsepower, min_hp=MIN_HP, max_hp=MAX_HP):
    # If min_hp and max_hp are still at their initial values, avoid the calculation
    if min_hp == float('inf') or max_hp == float('-inf'):
        normalized_hp = 0
    elif min_hp == max_hp:
        normalized_hp = 0  
    else:
        normalized_hp = (horsepower - min_hp) / (max_hp - min_hp)
        normalized_hp = np.clip(normalized_hp, 0, 1)
    
    mask = Image.new("L", empty_img.size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = full_img.size
    fill_height = int(normalized_hp * height)
    draw.rectangle([0, height - fill_height, width, height], fill=255)
    
    result_img = Image.composite(full_img, empty_img, mask)
    return result_img

###### MAIN CODE ######

# Infinite data generator that reads range data from the serial port
def infinite_data_generator(serial_connection):
    last_distance = None
    last_time = time.time()
    global last_hp, is_try_active, highest_hp_in_try, min_hp_observed, max_hp_observed, last_try_max_hp
    
    while True:
        try:
            line = serial_connection.readline().decode('utf-8').strip()
            current_time = time.time()
            current_distance = float(line)

            if last_distance is not None:
                time_diff = current_time - last_time if last_time else 1
                
                if abs(current_distance - last_distance) > DISTANCE_CHANGE_THRESHOLD:
                    speed_mps = (abs(current_distance - last_distance) / 1000) / time_diff
                    hp = calculate_horsepower(speed_mps)

                    # If a try is active, update the highest horsepower
                    if is_try_active:
                        if hp > highest_hp_in_try:
                            highest_hp_in_try = hp
                    else:
                        is_try_active = True  # Start a new try
                        highest_hp_in_try = hp  # Initialize with the current horsepower

                    last_hp = hp
                    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}, "
                          f"Data: {current_distance}, Speed: {speed_mps:.2f} m/s, Horsepower: {hp:.4f}")
                    
                    if min_hp_observed == float('inf'):
                        min_hp_observed = hp
                    if max_hp_observed == float('-inf'):
                        max_hp_observed = hp

                    yield hp
                else:
                    if is_try_active:
                        is_try_active = False
                        last_try_max_hp = highest_hp_in_try  # Save the max HP of the last try
                        yield 0  # Indicate the end of a try
                    else:
                        yield 0  # No significant change, yield 0 horsepower

            last_distance = current_distance
            last_time = current_time

        except ValueError:
            continue

##### PLOTTING ######

hp_data_generator = infinite_data_generator(serial_connection)

fig, (ax_img, ax_text) = plt.subplots(1, 2, figsize=(10, 5))

ax_img.axis('off')  # Hide axes for the image
ax_text.axis('off')  # Hide axes for the stats

img_display = ax_img.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))

hp_text = ax_text.text(0.5, 0.5, '', ha='center', va='center', fontsize=20, fontweight='bold', color='black')

min_hp_observed = float('inf')
max_hp_observed = float('-inf')

def update(frame):
    global min_hp_observed, max_hp_observed, last_hp, highest_hp_in_try, last_try_max_hp
    
    hp = next(hp_data_generator)

    if hp == 0:
        result_img = blend_images(0, min_hp=min_hp_observed, max_hp=max_hp_observed)
        hp_text.set_text(f'Horsepower: 0.0000\nLast Try Max HP: {last_try_max_hp:.4f}\nMax HP: {max_hp_observed:.4f}')
    else:
        if hp < min_hp_observed:
            min_hp_observed = hp
        if hp > max_hp_observed:
            max_hp_observed = hp
        
        result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
        hp_text.set_text(f'Horsepower: {hp:.4f}\nLast Try Max HP: {last_try_max_hp:.4f}\nMax HP: {max_hp_observed:.4f}')
    
    img_display.set_data(np.array(result_img))
    return [img_display, hp_text]

ani = animation.FuncAnimation(fig, update, frames=np.arange(0, 1000), blit=True, interval=50)
plt.show()
