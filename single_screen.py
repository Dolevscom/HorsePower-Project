import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager as fm
from matplotlib.gridspec import GridSpec
from PIL import Image, ImageDraw, ImageSequence
import numpy as np
from collections import deque  # For smoothing
from bidi.algorithm import get_display
import arabic_reshaper  # reshaping Hebrew text


###### CONSTANTS ######
CURRENT_WEIGHT = 7.5  # Weight of the object in kg
STARTING_DISTANCE = 1920
WHOLE_POLE_LEN = 116

MIN_HP = 0
MAX_HP = 0.1
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

translations = {
    'hebrew': {
        'lifted': 'הרמתם {weight} ק"ג לגובה {distance:.3f} ס"מ',
        'time': '\nתוך {time:.3f} שניות',
        'power': '\nההספק שהפקתם מגופכם הוא\n{watts:.3f} וואט = {hp:.3f} כח סוס'
    },
    'english': {
        'lifted': 'You lifted {weight} kg to a height of {distance:.3f} cm',
        'time': '\nIt took {time:.3f} seconds',
        'power': '\nThe power you produced is\n{watts:.3f} watts = {hp:.3f} horsepower'
    },
    'arabic': {
        'lifted': 'رفعت {weight} كغم إلى ارتفاع {distance:.3f} سم',
        'time': '\nاستغرقت {time:.3f} ثانية',
        'power': '\nالطاقة التي انتجتها هي\n{watts:.3f} واط = {hp:.3f} حصان'
    }
}


heading_text = {
    'hebrew': 'כח סוס',
    'english': 'Horsepower',
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
start_time = None  # To track the start time of the current try
reset_duration = 10 # Duration in seconds after which the display will reset
last_try_end_time = None


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

# Global variable to store the current fill level for smooth filling
current_fill_height = 0
def blend_images(horsepower, min_hp=MIN_HP, max_hp=MAX_HP, smoothing_factor=0.1):
    global current_fill_height

    # If min_hp or max_hp are not valid, set normalized_hp to 0
    if min_hp == float('inf') or max_hp == float('-inf'):
        normalized_hp = 0
    elif min_hp == max_hp:
        normalized_hp = 1 if horsepower >= max_hp else 0
    else:
        normalized_hp = (horsepower - min_hp) / (max_hp - min_hp)
    
    # Clip the value to be between 0 and 1
    normalized_hp = np.clip(normalized_hp, 0, 1)

    # Calculate the target fill height based on the normalized horsepower
    width, height = full_img.size
    target_fill_height = int(normalized_hp * height)

    # Smooth the transition towards the target fill height
    if target_fill_height > current_fill_height:
        current_fill_height += (target_fill_height - current_fill_height) * smoothing_factor
    else:
        current_fill_height -= (current_fill_height - target_fill_height) * smoothing_factor

    # Ensure the fill height is within bounds
    fill_height = max(1, int(current_fill_height))

    # Debug output to check the fill height calculations
    print(f"Normalized HP: {normalized_hp}, Target Fill Height: {target_fill_height}, Current Fill Height: {fill_height}")

    # Create the mask for blending
    mask = Image.new("L", empty_img.size, 0)
    draw = ImageDraw.Draw(mask)

    # Draw the fill on the mask from the bottom up
    draw.rectangle([0, height - fill_height, width, height], fill=255)

    # Create the blended image using the mask
    result_img = Image.composite(full_img, empty_img, mask)

    # Debug output to confirm the blending process
    print("Blended image updated based on current fill height.")

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
    ax1.text(0.5, 0.5, bidi_heading, ha='center', va='center', fontsize=80,
             fontproperties=fm.FontProperties(fname=font_paths[current_language]),
             fontweight='bold', color='black')
    ax1.axis('off')

    # Middle section for the text
    ax2 = fig.add_subplot(gs[1])
    hp_text = ax2.text(0.95, 0.95, '', ha='right', va='center', fontsize=30,
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


def get_translated_text(language, weight, distance, time, watts, hp):
    translation = translations.get(language, translations['hebrew'])
    lifted_text = translation['lifted'].format(weight=weight, distance=distance)
    time_text = translation['time'].format(time=time)
    power_text = translation['power'].format(watts=watts, hp=hp)
    return lifted_text + time_text + power_text


def reset_display():
    global last_hp, last_try_max_hp, last_try_max_distance, last_try_max_time_diff, is_try_active
    print("Resetting display after 25 seconds")
    last_hp = 0
    last_try_max_hp = 0
    last_try_max_distance = 0
    last_try_max_time_diff = 0
    is_try_active = False
    setup_measuring_screen()


def update_measuring_screen(frame):
    global min_hp_observed, max_hp_observed, last_hp, last_try_max_hp, last_try_max_distance,\
          last_try_max_time_diff, last_update_time, start_time, last_try_end_time

    current_time = time.time()

    # Check if enough time has passed since the last try ended for the reset
    if last_try_end_time is not None and (current_time - last_try_end_time) > 5:
        print("Resetting display after 5 seconds since the last try ended")
        reset_display()
        last_try_end_time = None  # Reset the end time to indicate no active try
        return [img_display, hp_text]

    # Only update if enough time has passed to reduce lag
    if current_time - last_update_time < update_interval:
        return [img_display, hp_text]  # Skip this update to avoid too frequent rendering

    last_update_time = current_time  # Update the time for the next frame

    if hp_data_generator:
        hp = next(hp_data_generator)
    else:
        hp = 0  # No serial data available, so default to 0 HP

    # If a new try has started, set the start_time
    if is_try_active and start_time is None:
        start_time = current_time

    # If a try ends, update the last_try_end_time
    if not is_try_active and start_time is not None:
        last_try_end_time = current_time
        start_time = None  # Reset start_time since the try ended

    # Use the last try's max HP for the display
    current_distance = (STARTING_DISTANCE - last_try_max_distance) / 100
    distance_in_cm = max(0, current_distance)

    watts = last_try_max_hp * WATTS_CONSTANT

    translated_text = get_translated_text(
        current_language,  # This is the selected language
        weight=CURRENT_WEIGHT,
        distance=distance_in_cm,
        time=last_try_max_time_diff,
        watts=watts,
        hp=last_try_max_hp,
    )

    reshaped_text = arabic_reshaper.reshape(translated_text) if current_language in ['arabic', 'hebrew'] else translated_text
    bidi_text = get_display(reshaped_text) if current_language in ['arabic', 'hebrew'] else reshaped_text

    # Set alignment based on the language
    if current_language == 'english':
        hp_text.set_ha('left')  # Align text to the left for English
        hp_text.set_position((0.05, 0.55))  # Position for left alignment
    else:
        hp_text.set_ha('right')  # Align text to the right for Hebrew/Arabic
        hp_text.set_position((0.95, 0.55))  # Position for right alignment

    hp_text.set_text(bidi_text)

    # Blend images based on the last try's max HP
    result_img = blend_images(last_try_max_hp)

    # Update the image display
    img_display.set_data(np.array(result_img))

    # Redraw the figure to ensure the update is applied
    plt.draw()

    return [img_display, hp_text]


def reset_display():
    """Resets the display to its initial state after a timeout."""
    global last_try_max_hp, last_try_max_distance, last_try_max_time_diff, start_time, is_try_active
    print("Resetting the display to initial state.")
    
    # Reset values
    last_try_max_hp = 0
    last_try_max_distance = 0
    last_try_max_time_diff = 0
    is_try_active = False
    start_time = None  # Reset the start_time

    # Reset the text and image display
    hp_text.set_text("")  # Clear text
    img_display.set_data(np.array(empty_img))  # Reset to the empty image

# Make sure to call `reset_display()` when initializing the screen
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