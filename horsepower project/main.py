import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from PIL import Image, ImageDraw
import numpy as np

# Set up the serial connection with the Arduino
serial_connection = serial.Serial('/dev/cu.usbserial-AR0JYRZK', 115200)  # Replace with your actual port

# Function to calculate horsepower from speed
def calculate_horsepower(speed_mps, weight=70):
    return (weight * speed_mps) / 745.7

# Load the images
empty_image_path = '/Users/dolevsmac/Desktop/SciMuse project/horsepower project/horse ilus/empty.png'
full_image_path = '/Users/dolevsmac/Desktop/SciMuse project/horsepower project/horse ilus/yellow.png'

empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")

# Ensure the images are the same size
empty_img = empty_img.resize(full_img.size)

# Function to blend images based on horsepower value
def blend_images(horsepower, min_hp=0, max_hp=100):
    if min_hp == max_hp:
        normalized_hp = 0  # Avoid NaN by setting to 0
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

# Infinite data generator that reads range data from the serial port
def infinite_data_generator(serial_connection):
    last_distance = None
    last_time = time.time()

    while True:
        try:
            line = serial_connection.readline().decode('utf-8').strip()
            current_time = time.time()
            current_distance = float(line)

            if last_distance is not None:
                time_diff = current_time - last_time if last_time else 1
                speed_mps = abs(current_distance - last_distance) / time_diff
                hp = calculate_horsepower(speed_mps)
                print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}, "
                      f"Data: {current_distance}, Speed: {speed_mps:.2f} m/s, Horsepower: {hp:.4f}")
                yield hp

            last_distance = current_distance
            last_time = current_time

        except ValueError:
            continue

hp_data_generator = infinite_data_generator(serial_connection)

# Set up the figure with two subplots: one for the animation and one for the stats
fig, (ax_img, ax_text) = plt.subplots(1, 2, figsize=(10, 5))

ax_img.axis('off')  # Hide axes for the image
ax_text.axis('off')  # Hide axes for the stats

# Initialize an empty image display on the axes
img_display = ax_img.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))

# Initialize a text display for the horsepower stats
hp_text = ax_text.text(0.5, 0.5, '', ha='center', va='center', fontsize=20, fontweight='bold', color='black')

min_hp_observed = float('inf')
max_hp_observed = float('-inf')

def update(frame):
    global min_hp_observed, max_hp_observed
    
    hp = next(hp_data_generator)
    
    # Update min/max only if necessary
    if hp < min_hp_observed:
        min_hp_observed = hp
    if hp > max_hp_observed:
        max_hp_observed = hp
    
    result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
    
    # Update the image in the plot
    img_display.set_data(np.array(result_img))
    
    # Update the horsepower stats text
    hp_text.set_text(f'Horsepower: {hp:.4f}\nMax HP: {max_hp_observed:.4f}')
    
    return [img_display, hp_text]

# Set up the animation loop
ani = animation.FuncAnimation(fig, update, frames=np.arange(0, 1000), blit=True, interval=50)
plt.show()
