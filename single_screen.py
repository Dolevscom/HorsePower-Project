import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager as fm
import matplotlib.image as mpimg
from matplotlib.gridspec import GridSpec
from PIL import Image, ImageDraw, ImageSequence
import numpy as np
from collections import deque  # For smoothing
from bidi.algorithm import get_display
import arabic_reshaper  # reshaping Hebrew text
import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

###### CONSTANTS ######
CURRENT_WEIGHT = 7.5  # Weight of the object in kg
STARTING_DISTANCE = 1920
WHOLE_POLE_LEN = 116

MIN_HP = 0
MAX_HP = 0.01
DISTANCE_CHANGE_THRESHOLD = 10  # Lowered threshold for more sensitivity
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

# ARDUINO_PORT = 'COM4'
# # Load local files
# empty_image_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\Empty horse.jpg'
# full_image_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\Full horse.jpg'
# gif_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\introduction gif.gif'

# # Font paths for different languages (ensure fonts are available for all languages)
# font_paths = {
#     'hebrew': r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
#     'english': r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
#     'arabic': r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\fonts\NotoKufiArabic-SemiBold.ttf'  # Use a font that supports Arabic
# }

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
distance_buffer = deque(maxlen=5)  # For smoothing the distance readings
last_update_time = time.time()  # Global variable to store last update time
update_interval = 0.2  # Update every 0.2 seconds to reduce frequency of updates

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

def blend_images(horsepower, min_hp=0, max_hp=0.1):
    # Ensure horsepower is normalized between 0 and 1, capping at 1 HP
    normalized_hp = min(horsepower / max_hp, 1.0)  # Cap the horsepower to a max of 1

    # Create the mask for blending
    mask = Image.new("L", empty_img.size, 0)
    draw = ImageDraw.Draw(mask)
    width, height = full_img.size

    # Calculate the height to fill based on the normalized horsepower
    fill_height = int(normalized_hp * height)

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

    # print("Starting data generator...")  # Debugging print

    while True:
        if serial_connection and serial_connection.in_waiting > 0:  # Check if there's data to read
            raw_data = serial_connection.read(serial_connection.in_waiting).decode('utf-8').strip()
            # print(f"Raw data received from Arduino: {raw_data}")  # Debugging print
            data_lines = raw_data.splitlines()
            current_time = time.time()

            for line in data_lines:
                try:
                    current_distance = float(line.strip())  # Convert the line to a float
                    distance_buffer.append(current_distance)  # Add to smoothing buffer
                    smoothed_distance = sum(distance_buffer) / len(distance_buffer)  # Smoothed distance
                    # print(f"Parsed distance from Arduino: {smoothed_distance} mm")  # Debugging print

                    if last_distance is None:
                        # print("First distance reading received.")
                        last_distance = smoothed_distance
                        last_time = current_time
                        continue

                    time_diff = max(current_time - last_time, 0.001)
                    # print(f"Time difference: {time_diff} seconds")  # Debugging print

                    # Skip if the time difference is too small (e.g., less than 0.05 seconds)
                    if time_diff < 0.05:
                        continue

                    if abs(smoothed_distance - last_distance) > DISTANCE_CHANGE_THRESHOLD:
                        speed_mps = (abs(smoothed_distance - last_distance) / 1000) / time_diff
                        # print(f"Speed: {speed_mps} m/s")  # Debugging print

                        hp = calculate_horsepower(speed_mps)
                        # print(f"Calculated horsepower: {hp}")  # Debugging print

                        if is_try_active:
                            if hp > highest_hp_in_try:
                                highest_hp_in_try = hp
                                # print(f"New highest HP in this try: {highest_hp_in_try}")  # Debugging print
                        else:
                            is_try_active = True  # Start a new try
                            try_start_time = current_time  # Record the start time of the try
                            highest_hp_in_try = hp
                            print("New try started")  # Debugging print

                        last_hp = hp
                        yield hp
                    else:
                        if is_try_active:
                            is_try_active = False
                            last_try_max_hp = highest_hp_in_try  # Save the max HP of the last try
                            last_try_max_time_diff = current_time - try_start_time if try_start_time else 0
                            last_try_max_distance = abs(smoothed_distance - last_distance)
                            print(f"Try ended. Max HP: {last_try_max_hp}, Max Distance: {last_try_max_distance}, Time diff: {last_try_max_time_diff}")  # Debugging print
                            try_start_time = None
                            yield 0
                        else:
                            yield 0
                except ValueError:
                    continue

                last_distance = smoothed_distance
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
    ax1.text(0.5, 0.75, bidi_heading, ha='center', va='center', fontsize=80,
             fontproperties=fm.FontProperties(fname=font_paths[current_language]),
             fontweight='bold', color='black')
    ax1.axis('off')

    # Middle section for the text
    ax2 = fig.add_subplot(gs[1])
    hp_text = ax2.text(0.95, 0.75, '', ha='right', va='center', fontsize=30,
                       fontproperties=fm.FontProperties(fname=font_paths[current_language]),
                       color='black', fontweight='regular', transform=ax.transAxes, zorder=2,
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
def get_translated_text(language, weight, distance, time, watts, hp, last_distance):
    translation = translations.get(language, translations['hebrew'])
    lifted_text = translation['lifted'].format(weight=weight, distance=last_distance)  # Using last_distance
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

    # Use the last try's max HP for the display, as requested
    current_distance = (STARTING_DISTANCE - last_try_max_distance) / 100
    distance_in_cm = max(0, current_distance)

    translated_text = get_translated_text(
        current_language,  # This is the selected language
        weight=CURRENT_WEIGHT,
        distance=distance_in_cm,
        time=last_try_max_time_diff,
        watts=last_try_max_hp * WATTS_CONSTANT,
        hp=last_try_max_hp,
        last_distance=last_try_max_distance  # Display the last try's distance
    )

    reshaped_text = arabic_reshaper.reshape(translated_text) if current_language in ['arabic', 'hebrew'] else translated_text
    bidi_text = get_display(reshaped_text) if current_language in ['arabic', 'hebrew'] else reshaped_text
    hp_text.set_text(bidi_text)
    
    # Set alignment based on the language
    if current_language == 'english':
        hp_text.set_ha('left')  # Align text to the left for English
        hp_text.set_position((0.05, 0.55))  # Position for left alignment
    else:
        hp_text.set_ha('right')  # Align text to the right for Hebrew/Arabic
        hp_text.set_position((0.95, 0.55))  # Position for right alignment
    # Blend the images based on the normalized horsepower
    result_img = blend_images(last_try_max_hp)  # last_try_max_hp is used for the visualization
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