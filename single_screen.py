import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager as fm
import matplotlib.image as mpimg
from matplotlib.gridspec import GridSpec
from PIL import Image, ImageDraw, ImageSequence
import numpy as np
from bidi.algorithm import get_display
import arabic_reshaper  # reshaping Hebrew text
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

###### CONSTANTS ######
CURRENT_WEIGHT = 6  # Weight of the object in kg
STARTING_DISTNACE = 1920
WHOLE_POLE_LEN = 116

MIN_HP = 0
MAX_HP = 0.01
DISTANCE_CHANGE_THRESHOLD = 30
WATTS_CONSTANT = 745.7

######################### ***SHOULD BE CHANGED BETWEEN DIFFERENT COMPUTERS*** #########################
ARDUINO_PORT = 'COM5'
# Load local files
empty_image_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\Empty horse.jpg'
full_image_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\Full horse.jpg'
gif_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\opening.gif'

# Font paths for different languages (ensure fonts are available for all languages)
font_paths = {
    'hebrew': r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
    'english': r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
    'arabic': r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\NotoKufiArabic-SemiBold.ttf'  # Use a font that supports Arabic
}

# Translation dictionary
translations = {
    'hebrew': {
        'lifted': 'הרמתם {weight} ק"ג לגובה {distance:.3f} ס"מ',
        'time': '\nתוך {time:.3f} שניות',
        'power': '\nההספק שהפקתם מגופכם הוא {watts:.3f} וואט',
        'horsepower': '\nשהם {hp:.3f} כח סוס'
    },
    'english': {
        'lifted': 'You lifted {weight} kg to a height of {distance:.3f} cm',
        'time': '\nIt took {time:.3f} seconds',
        'power': '\nThe power you produced is {watts:.3f} watts',
        'horsepower': '\nThat is {hp:.3f} horsepower'
    },
    'arabic': {
        'lifted': 'رفعت {weight} كغم إلى ارتفاع {distance:.3f} سم',
        'time': '\nاستغرقت {time:.3f} ثانية',
        'power': '\nالطاقة التي انتجتها هي {watts:.3f} واط',
        'horsepower': '\nوهي تعادل {hp:.3f} حصان'
    }
}

heading_text = {
    'hebrew': 'תוצאות כח סוס',
    'english': 'Horsepower Results',
    'arabic': 'نتائج قوة الحصان'
}

# List of available languages
languages = ['hebrew', 'english', 'arabic']
current_language_index = 0  # Start with Hebrew
current_language = languages[current_language_index]  # Initial language is Hebrew

# Load assets
empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")
empty_img = empty_img.resize(full_img.size)  # Ensure the images are the same size
gif_frames = [frame.copy() for frame in ImageSequence.Iterator(Image.open(gif_path))]
width, height = full_img.size
aspect_ratio = width / height

##### GLOBALS ######
last_hp = 0  # Global variable to store the last horsepower value
is_try_active = False  # To track if a "try" is ongoing
highest_hp_in_try = 0  # To store the highest horsepower during a "try"
last_try_max_hp = 0  # To store the max horsepower of the last try
last_try_max_distance = 0  # To store the distance of the last try's max horsepower
last_try_max_time_diff = 0  # To store the time difference of the last try's max horsepower
min_hp_observed = float('inf')
max_hp_observed = float('-inf')
ani_measuring = None  # Keep animation object persistent

# Set up the serial connection with the Arduino
try:
    serial_connection = serial.Serial(ARDUINO_PORT, 115200, timeout=1)
except (serial.SerialException, FileNotFoundError, PermissionError) as e:
    print(f"Error opening serial port: {e}")
    serial_connection = None  # Set to None if serial connection fails

###### HELPER FUNCTIONS ######

# Function to calculate horsepower from speed
def calculate_horsepower(speed_mps):
    return (CURRENT_WEIGHT * speed_mps) / WATTS_CONSTANT

def blend_images(horsepower, min_hp=MIN_HP, max_hp=MAX_HP):
    # Ensure horsepower is normalized between 0 and 1
    if min_hp == float('inf') or max_hp == float('-inf'):
        normalized_hp = 0
    elif min_hp == max_hp:
        normalized_hp = 1 if horsepower >= max_hp else 0
    else:
        normalized_hp = (horsepower - min_hp) / (max_hp - min_hp)
    
    # Clip the value to be between 0 and 1
    normalized_hp = np.clip(normalized_hp, 0, 1)

    # Create the mask for blending
    mask = Image.new("L", empty_img.size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = full_img.size

    # Calculate the height to fill based on the normalized horsepower
    fill_height = int(normalized_hp * height)

    # Ensure the entire image is filled when horsepower is at max
    fill_height = max(1, fill_height)  # Avoid a 0 height

    # Draw the fill on the mask from the bottom up
    draw.rectangle([0, height - fill_height, width, height], fill=255)

    # Create the blended image using the mask
    result_img = Image.composite(full_img, empty_img, mask)

    return result_img

###### MAIN CODE ######

def infinite_data_generator(serial_connection):
    last_distance = None
    last_time = time.time()
    try_start_time = None  # Variable to track the start time of a try
    global last_hp, is_try_active, highest_hp_in_try, min_hp_observed, max_hp_observed, last_try_max_hp, last_try_max_time_diff, last_try_max_distance

    print("Starting data generator...")  # Debugging print

    while True:
        if serial_connection and serial_connection.in_waiting > 0:  # Check if there's data to read
            raw_data = serial_connection.read(serial_connection.in_waiting).decode('utf-8').strip()
            data_lines = raw_data.splitlines()
            current_time = time.time()
            for line in data_lines:
                try:
                    current_distance = float(line.strip())  # Convert the line to a float
                except ValueError:
                    continue

                if last_distance is not None:
                    time_diff = max(current_time - last_time, 0.001) if last_time else 1
                    if abs(current_distance - last_distance) > DISTANCE_CHANGE_THRESHOLD:
                        speed_mps = (abs(current_distance - last_distance) / 1000) / time_diff
                        hp = calculate_horsepower(speed_mps)

                        if is_try_active:
                            if hp > highest_hp_in_try:
                                highest_hp_in_try = hp
                        else:
                            is_try_active = True  # Start a new try
                            try_start_time = current_time  # Record the start time of the try
                            highest_hp_in_try = hp

                        last_hp = hp
                        yield hp
                    else:
                        if is_try_active:
                            is_try_active = False
                            last_try_max_hp = highest_hp_in_try  # Save the max HP of the last try
                            last_try_max_time_diff = current_time - try_start_time if try_start_time else 0
                            last_try_max_distance = abs(current_distance - last_distance)
                            try_start_time = None
                            yield 0
                        else:
                            yield 0
                last_distance = current_distance
                last_time = current_time

##### PLOTTING ######

hp_data_generator = infinite_data_generator(serial_connection) if serial_connection else None
fig, ax = plt.subplots(figsize=(8, 8/aspect_ratio))
ax.axis('off')
img_display = ax.imshow(np.zeros((height, width, 4), dtype=np.uint8))
hp_text = ax.text(0.5, 0.9, '', ha='center', va='center', fontsize=30,
                  fontweight='bold', color='black', 
                  bbox=dict(facecolor='lightgray',
                            edgecolor='black', boxstyle='round,pad=0.5'))

fig.patch.set_visible(False)

##### SETUP AND UPDATE SCREENS ######

# GLOBALS
ani_measuring = None  # Keep animation object persistent

def setup_measuring_screen():
    global img_display, hp_text, ani_measuring  # Make ani_measuring global

    print("Setting up measuring screen...")  # Debugging print
    fig.clear()
    gs = GridSpec(3, 1, height_ratios=[3, 1, 3])  # Define 3 rows with different height ratios
    
    # Top section for the heading
    ax1 = fig.add_subplot(gs[0])
    heading = heading_text[current_language]
    reshaped_heading = arabic_reshaper.reshape(heading) if current_language in ['arabic', 'hebrew'] else heading
    bidi_heading = get_display(reshaped_heading) if current_language in ['arabic', 'hebrew'] else reshaped_heading
    ax1.text(0.5, 0.5, bidi_heading, ha='center', va='center', fontsize=35,
             fontproperties=fm.FontProperties(fname=font_paths[current_language]),
             fontweight='bold', color='black')
    ax1.axis('off')

    # Middle section for the text
    ax2 = fig.add_subplot(gs[1])
    hp_text = ax2.text(0.95, 0.55, '', ha='right', va='center', fontsize=15,
                       fontproperties=fm.FontProperties(fname=font_paths[current_language]),
                       color='black', fontweight='bold', transform=ax.transAxes, zorder=2,
                       bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    ax2.axis('off')

    # Bottom section for the full/empty images
    ax3 = fig.add_subplot(gs[2])
    img_display = ax3.imshow(np.zeros((height, width, 4), dtype=np.uint8))  # Placeholder for empty/full images
    ax3.axis('off')

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0, hspace=0, wspace=0)
    plt.tight_layout(pad=0, h_pad=0, w_pad=0)

    fig.patch.set_visible(False)

    # Create animation, keep it persistent to avoid garbage collection
    if ani_measuring is None:  # Only create the animation if it doesn't already exist
        ani_measuring = animation.FuncAnimation(fig, update_measuring_screen, frames=100, interval=200, blit=False)
    
    plt.draw()  # Redraw the figure


# Function to retrieve the correct text in the selected language
def get_translated_text(language, weight, distance, time, watts, hp):
    translation = translations.get(language, translations['hebrew'])
    lifted_text = translation['lifted'].format(weight=weight, distance=distance)
    time_text = translation['time'].format(time=time)
    power_text = translation['power'].format(watts=watts)
    horsepower_text = translation['horsepower'].format(hp=hp)
    return lifted_text + time_text + power_text + horsepower_text

def update_measuring_screen(frame):
    global min_hp_observed, max_hp_observed, last_hp, last_try_max_hp, last_try_max_distance, last_try_max_time_diff

    if hp_data_generator:
        hp = next(hp_data_generator)
    else:
        hp = 0  # No serial data available, so default to 0 HP

    current_distance = (STARTING_DISTNACE - last_try_max_distance) / 100
    distance_in_cm = 0 if (current_distance <= ((STARTING_DISTNACE / 100) + 2)) else current_distance

    translated_text = get_translated_text(
        current_language,  # This is the selected language
        weight=CURRENT_WEIGHT,
        distance=distance_in_cm,
        time=last_try_max_time_diff,
        watts=last_try_max_hp * WATTS_CONSTANT,
        hp=last_try_max_hp
    )

    reshaped_text = arabic_reshaper.reshape(translated_text) if current_language in ['arabic', 'hebrew'] else translated_text
    bidi_text = get_display(reshaped_text) if current_language in ['arabic', 'hebrew'] else reshaped_text
    hp_text.set_text(bidi_text)

    result_img = blend_images(hp if hp != 0 else 0)
    img_display.set_data(np.array(result_img))

    return [img_display, hp_text]

setup_measuring_screen()

# Function to change language based on spacebar press
def change_language_on_key(event):
    global current_language, current_language_index
    
    if event.key == ' ':
        current_language_index = (current_language_index + 1) % len(languages)
        current_language = languages[current_language_index]
        print(f"Language switched to: {current_language}")
        
        setup_measuring_screen()  # Reload screen with the new language and heading
        plt.draw()  # Redraw the figure

fig.canvas.mpl_connect('key_press_event', change_language_on_key)

# Start the main loop
plt.show()
