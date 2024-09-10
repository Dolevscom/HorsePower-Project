import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from PIL import Image, ImageDraw, ImageSequence
import numpy as np

###### CONSTANTS ######
CURRENT_WEIGHT = 1.525  # Weight of the object in kg
# CURRENT_WEIGHT = 4.519  # Weight of the object in kg
# CURRENT_WEIGHT = 7  # Weight of the object in kg

MIN_HP = 0
MAX_HP = 100
DISTANCE_CHANGE_THRESHOLD = 30
last_hp = 0
is_try_active = False
highest_hp_in_try = 0
last_try_max_hp = 0

# Set up the serial connection with the Arduino
serial_connection = serial.Serial('COM3', 115200, timeout=1)

# Load the images
empty_image_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\horse ilus\empty.png'
full_image_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\horse ilus\yellow.png'
gif_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\.gif'

empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")
empty_img = empty_img.resize(full_img.size)

# Load GIF
gif_frames = [frame.copy() for frame in ImageSequence.Iterator(Image.open(gif_path))]

###### HELPER FUNCTIONS ######

def calculate_horsepower(speed_mps):
    return (CURRENT_WEIGHT * speed_mps) / 745.7

def blend_images(horsepower, min_hp=MIN_HP, max_hp=MAX_HP):
    normalized_hp = (horsepower - min_hp) / (max_hp - min_hp) if min_hp != max_hp else 0
    normalized_hp = np.clip(normalized_hp, 0, 1)
    mask = Image.new("L", empty_img.size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = full_img.size
    fill_width = int(normalized_hp * width)  # Fill from right to left
    draw.rectangle([width - fill_width, 0, width, height], fill=255)
    result_img = Image.composite(full_img, empty_img, mask)
    return result_img

###### MAIN CODE ######

# Generator to read range data from the serial port
def infinite_data_generator(serial_connection):
    last_distance = None
    last_time = time.time()
    global last_hp, is_try_active, highest_hp_in_try, min_hp_observed, max_hp_observed, last_try_max_hp
    
    while True:
        try:
            line = serial_connection.readline().decode('utf-8').strip()
            current_time = time.time()
            current_distance = float(line)
            time_diff = max(current_time - last_time, 0.001)
            
            if abs(current_distance - last_distance) > DISTANCE_CHANGE_THRESHOLD:
                speed_mps = (abs(current_distance - last_distance) / 1000) / time_diff
                hp = calculate_horsepower(speed_mps)
                if is_try_active:
                    if hp > highest_hp_in_try:
                        highest_hp_in_try = hp
                else:
                    is_try_active = True
                    highest_hp_in_try = hp
                last_hp = hp
                yield hp
            else:
                if is_try_active:
                    is_try_active = False
                    last_try_max_hp = highest_hp_in_try
                    yield 0
                else:
                    yield 0

            last_distance = current_distance
            last_time = current_time

        except ValueError:
            continue

# PLOTTING ######
hp_data_generator = infinite_data_generator(serial_connection)

fig, ax = plt.subplots()
img_display = ax.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))

# Track which screen is active
current_screen = 'opening'

# Min and max observed horsepower values
min_hp_observed = float('inf')
max_hp_observed = float('-inf')

def on_click(event):
    global current_screen
    if current_screen == 'opening':
        # Switch to measuring screen on mouse click
        current_screen = 'measuring'
        plt.clf()
        setup_measuring_screen()
        
def update_opening_screen(frame):
    ax.clear()
    ax.imshow(gif_frames[frame % len(gif_frames)])
    ax.text(0.5, 0.8, 'Click to start measuring horsepower.', fontsize=20, ha='center', va='center')
    return [ax]

def setup_measuring_screen():
    global img_display, hp_text
    
    ax_img, ax_text = fig.subplots(1, 2, figsize=(10, 5))
    ax_img.axis('off')
    ax_text.axis('off')
    img_display = ax_img.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))
    hp_text = ax_text.text(0.5, 0.5, '', ha='center', va='center', fontsize=20, fontweight='bold')

def update_measuring_screen(frame):
    global min_hp_observed, max_hp_observed, last_hp, highest_hp_in_try, last_try_max_hp
    hp = next(hp_data_generator)
    
    if hp == 0:
        result_img = blend_images(0, min_hp=min_hp_observed, max_hp=max_hp_observed)
        hp_text.set_text(f'כח סוס : 0.0000\nניסיון אחרון: {last_try_max_hp:.4f}\nמקסימום: {max_hp_observed:.4f}')
    else:
        min_hp_observed = min(min_hp_observed, hp)
        max_hp_observed = max(max_hp_observed, hp)
        result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
        hp_text.set_text(f'כח סוס: {hp:.4f}\nניסיון אחרון: {last_try_max_hp:.4f}\nמקסימום: {max_hp_observed:.4f}')
    
    img_display.set_data(np.array(result_img))
    return [img_display, hp_text]

# Initial animation for the opening screen
ani_opening = animation.FuncAnimation(fig, update_opening_screen, frames=len(gif_frames), interval=100, repeat=True)
fig.canvas.mpl_connect('button_press_event', on_click)

plt.show()
