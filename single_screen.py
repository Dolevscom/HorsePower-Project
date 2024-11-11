import serial
import time
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager as fm
from matplotlib.gridspec import GridSpec
from PIL import Image, ImageDraw, ImageSequence
import numpy as np
from screeninfo import get_monitors
from collections import deque  # For smoothing
from bidi.algorithm import get_display
import arabic_reshaper  # reshaping Hebrew text
import sys
import atexit
import logging

# Set up Matplotlib to use TkAgg backend for compatibility with screen updates
matplotlib.use("TkAgg")


###### CONSTANTS ######


CURRENT_WEIGHT = 7.5  # Object weight in kg
STARTING_DISTANCE = 1870  # Starting distance for calculations in mm
WHOLE_POLE_LEN = 116  # Length of the pole for horsepower calculation
MIN_HP = 0  # Minimum horsepower threshold
MAX_HP = 1  # Maximum horsepower threshold
DISTANCE_CHANGE_THRESHOLD = 10  # Threshold to detect significant distance changes
WATTS_CONSTANT = 745.7  # Constant for horsepower to watts conversion
WEIGHT_TO_FORCE_CONST = 9.81  # Gravity constant to convert weight to force
METER_TO_FEET_CONST = 3.28084  # Conversion constant from meters to feet
SECONDS_TO_MINUTE = 60  # Conversion from seconds to minutes

######################### ***SHOULD BE CHANGED BETWEEN DIFFERENT COMPUTERS*** #########################
 
####### [computer upstairs] ########


# ARDUINO_PORT = 'COM5'
# # Load local files
# empty_image_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\Empty horse.jpg'
# full_image_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\Full horse.jpg'
# gif_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\opening.gif'


# # Font paths for different languages (ensure fonts are available for all languages)
# font_paths = {
#     'hebrew': r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
#     'english': r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
#     'arabic': r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\NotoKufiArabic-SemiBold.ttf'  # Use a font that supports Arabic
# }   


####### [computer in the workshop] ########

ARDUINO_PORT = 'COM5'
# Load local files
# empty_image_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\empty_horse_bar.jpg'
# full_image_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\full_horse_bar.jpg'

empty_image_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\Empty horse.jpg'
full_image_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\Full horse.jpg'
gif_path = r'C:\Users\MakeMada\Desktop\HP project\horsepower project\introduction gif.gif'

# Font paths for different languages (ensure fonts are available for all languages)
font_paths = {
    'hebrew': r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
    'english': r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf',
    'arabic': r'C:\Users\MakeMada\Desktop\HP project\horsepower project\assets\fonts\NotoKufiArabic-SemiBold.ttf'  # Use a font that supports Arabic
}




######################### LANGUAGES #########################


translations = {
    'hebrew': {
        'lifted': 'הרמתם {weight} ק"ג לגובה {distance:.1f} ס"מ',
        'time': '\nתוך {time:.1f} שניות',
        'power': '\nההספק שהפקתם מגופכם הוא\n{watts:.1f} וואט = {hp:.1f} כח סוס'
    },
    'english': {
        'lifted': 'You lifted {weight} kg to a height of {distance:.1f} cm',
        'time': '\nIt took {time:.1f} seconds',
        'power': '\nThe power you produced is\n{watts:.1f} watts = {hp:.1f} horsepower'
    },
    'arabic': {
        'lifted': 'رفعت {weight} كغم إلى ارتفاع {distance:.1f} سم',
        'time': '\nاستغرقت {time:.1f} ثانية',
        'power': '\nالطاقة التي انتجتها هي\n{watts:.1f} واط = {hp:.1f} حصان'
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


###### GLOBAL VARIABLES ######



last_hp = 0  # Global variable to store the last horsepower value
is_try_active = False  # To track if a "try" is ongoing
highest_hp_in_try = 0  # To store the highest horsepower during a "try"
last_try_max_hp = 0  # To store the max horsepower of the last try
last_try_max_distance = 0  # To store the distance of the last try's max horsepower
last_try_max_time_diff = 0  # To store the time difference of the last try's max horsepower
ani_measuring = None  # Keep animation object persistent
distance_buffer = deque(maxlen=5)  # For smoothing the distance readings
last_update_time = time.time()  # Global variable to store last update time
update_interval = 0.2  # Update every 0.2 seconds to reduce frequency of updates
start_time = None  # To track the start time of the current try
reset_duration = 15 # Duration in seconds after which the display will reset
last_try_end_time = None
current_fill_height = 0
last_rise_time = time.time()
is_rising = True



###### SERIAL CONNECTION ######

# Set up the serial connection with the Arduino
try:
    serial_connection = serial.Serial(ARDUINO_PORT, 115200, timeout=1)
except (serial.SerialException, FileNotFoundError, PermissionError) as e:
    print(f"Error opening serial port: {e}")
    serial_connection = None  # Set to None if serial connection fails


###### HELPER FUNCTIONS ######

def get_secondary_monitor():
    """Identify and return the secondary monitor for display if available, otherwise return primary."""
    monitors = get_monitors()
    if len(monitors) > 1:
        print(f"Secondary monitor detected: {monitors[1]}")
        return monitors[1]
    else:
        print(f"Only one monitor detected, using primary: {monitors[0]}")
        return monitors[0]  # Falls back to the primary monitor if no secondary detected



def calculate_horsepower(distance_meters, time_seconds):
    """Calculate horsepower based on distance and time."""
    # Convert weight to force in Newtons (N)
    F = CURRENT_WEIGHT * 9.81  # Force in Newtons
    # Calculate horsepower in metric units and convert to horsepower
    hp = (F * distance_meters) / (time_seconds * 745.7) if time_seconds != 0 else 0
    # print(f"Calculating Horsepower - Distance (m): {distance_meters:.4f}, Time (s): {time_seconds:.4f}, "
    #       f"Force (N): {F:.2f}, Horsepower (hp): {hp:.4f}")
    return hp
    

def blend_images(horsepower, min_hp=0, max_hp=1, rise_smoothing=0.5, fall_smoothing=0.5, hold_time=0.1):
    """
    Blends two images (empty and full) with a filling effect from bottom to top based on the horsepower.
    
    Parameters:
        horsepower (float): The current horsepower value.
        min_hp (float): Minimum horsepower (defaults to 0).
        max_hp (float): Maximum horsepower (defaults to 1).
        rise_smoothing (float): Smoothing factor for the fill rising.
        fall_smoothing (float): Smoothing factor for the fill falling.
        hold_time (float): Time in seconds to hold at the peak before falling.

    Returns:
        PIL.Image: The resulting image with the applied fill effect.
    """
    global current_fill_height, last_rise_time, is_rising

    # Clamp horsepower between min and max, then normalize to a 0-1 range
    normalized_hp = max(0, min(1, (horsepower - min_hp) / (max_hp - min_hp)))

    # Determine the target fill height based on normalized horsepower
    width, height = full_img.size
    target_fill_height = int(normalized_hp * height)

    # Manage rising and falling of the fill
    if is_rising:
        # Smooth rise towards the target height
        current_fill_height += (target_fill_height - current_fill_height) * rise_smoothing

        # Check if target height is reached
        if current_fill_height >= target_fill_height:
            last_rise_time = time.time()  # Record time at peak
            is_rising = False  # Stop rising and start hold phase
    else:
        # Begin falling if hold time has elapsed
        if time.time() - last_rise_time > hold_time:
            current_fill_height -= current_fill_height * fall_smoothing  # Smooth descent

    # Ensure fill height stays within image bounds
    fill_height = max(1, min(height, int(current_fill_height)))

    # Create a mask to show the fill from bottom to top
    mask = Image.new("L", empty_img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle([0, height - fill_height, width, height], fill=255)

    # Blend images using the mask
    result_img = Image.composite(full_img, empty_img, mask)

    # Reset rising if horsepower is zero
    if horsepower <= min_hp:
        is_rising = True

    return result_img



###### MAIN CODE AND DATA GENERATION ######

def infinite_data_generator(serial_connection):
    """
    Generator to read data from Arduino and calculate horsepower.
    Handles 'try' events and updates horsepower values based on distance changes.
    """
    last_distance = None
    last_time = time.time()
    try_start_time = None  # Variable to track the start time of a try
    global last_hp, is_try_active, highest_hp_in_try, last_try_max_hp, last_try_max_time_diff, last_try_max_distance
    global current_language, current_language_index

    closest_distance_in_try = STARTING_DISTANCE

    while True:
        if serial_connection and serial_connection.in_waiting > 0:  # Check if there's data to read
            raw_data = serial_connection.read(serial_connection.in_waiting).decode('utf-8').strip()
            data_lines = raw_data.splitlines()
            current_time = time.time()

            for line in data_lines:
                # Check for the special command to switch language
                if line == "SPACE":
                    # Switch language and update the display
                    current_language_index = (current_language_index + 1) % len(languages)
                    current_language = languages[current_language_index]
                    print(f"Language switched to: {current_language}")
                    setup_measuring_screen()
                    plt.draw()
                    continue  # Skip further processing for this loop iteration

                try:
                    current_distance = float(line.strip())  # Convert the line to a float
                    distance_buffer.append(current_distance)  # Add to smoothing buffer
                    smoothed_distance = sum(distance_buffer) / len(distance_buffer)  # Smoothed distance
                    print(f"Raw Distance: {current_distance} mm, Smoothed Distance: {smoothed_distance} mm, in cm {current_distance/10}")

                    if last_distance is None:
                        last_distance = smoothed_distance
                        last_time = current_time
                        continue

                    time_diff = max(current_time - last_time, 0.001)

                    # Skip if the time difference is too small (e.g., less than 0.05 seconds)
                    if time_diff < 0.05:
                        continue

                    # Calculate distance moved in meters
                    distance_moved_meters = abs(smoothed_distance - last_distance) / 1000  # Convert mm to meters

                    if distance_moved_meters > (DISTANCE_CHANGE_THRESHOLD / 1000):  # Check threshold in meters
                        # Calculate horsepower based on the distance moved and time
                        hp = calculate_horsepower(distance_moved_meters, time_diff)

                        if is_try_active:
                            # Update the closest distance in this try if current distance is closer to the sensor
                            if smoothed_distance < closest_distance_in_try:
                                closest_distance_in_try = smoothed_distance

                            # Track the maximum horsepower in this try
                            if hp > highest_hp_in_try:
                                highest_hp_in_try = hp
                        else:
                            # Start a new try
                            is_try_active = True
                            try_start_time = current_time
                            closest_distance_in_try = smoothed_distance
                            highest_hp_in_try = hp

                        last_hp = hp
                        yield hp
                    else:
                        if is_try_active:
                            # End the try and calculate max distance
                            is_try_active = False
                            last_try_max_hp = highest_hp_in_try
                            last_try_max_time_diff = current_time - try_start_time if try_start_time else 0
                            last_try_max_distance = STARTING_DISTANCE - closest_distance_in_try
                            try_start_time = None
                            yield 0
                        else:
                            yield 0
                except ValueError:
                    continue

                last_distance = smoothed_distance
                last_time = current_time



##### PLOTTING ######

def open_on_secondary_monitor():
    """Display figure on the secondary monitor if available."""
    secondary_monitor = get_secondary_monitor()
    fig, ax = plt.subplots(figsize=(8, 8 / (secondary_monitor.width / secondary_monitor.height)))
    ax.axis('off')
    
    # Move the figure to the second screen and make it full screen
    backend = plt.get_backend()
    mng = plt.get_current_fig_manager()

    if backend == 'TkAgg':
        print(f"Using TkAgg backend. Setting geometry to secondary monitor at coordinates ({secondary_monitor.x}, {secondary_monitor.y})")
        mng.window.wm_geometry(f"+{secondary_monitor.x}+{secondary_monitor.y}")
        mng.resize(secondary_monitor.width, secondary_monitor.height)
    elif backend in ['Qt5Agg', 'QtAgg']:
        print(f"Using Qt5Agg or QtAgg backend. Setting geometry to secondary monitor at coordinates ({secondary_monitor.x}, {secondary_monitor.y})")
        mng.window.setGeometry(secondary_monitor.x, secondary_monitor.y, secondary_monitor.width, secondary_monitor.height)
    else:
        print(f"Using unsupported backend: {backend}. The window may not display on the secondary monitor.")
    
    return fig, ax

# Initialize data generator
hp_data_generator = infinite_data_generator(serial_connection) if serial_connection else None
fig, ax = open_on_secondary_monitor()
img_display = ax.imshow(np.zeros((height, width, 4), dtype=np.uint8))




##### SETUP AND UPDATE SCREENS ######



def setup_measuring_screen():
    """Initialize the layout for the measuring screen with sections for heading, text, and image."""
    global img_display, hp_text, ani_measuring  # Make ani_measuring global
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


###### EVENT HANDLING AND DISPLAY UPDATE ######

# Function to change language based on spacebar press
def change_language_on_key(event):
    """Change display language when spacebar is pressed."""
    global current_language, current_language_index
   
    if event.key == ' ':
        current_language_index = (current_language_index + 1) % len(languages)
        current_language = languages[current_language_index]
        # print(f"Language switched to: {current_language}")
       
        setup_measuring_screen()  # Reload screen with the new language and heading
        plt.draw()  # Redraw the figure


fig.canvas.mpl_connect('key_press_event', change_language_on_key)


def get_translated_text(language, weight, distance, time, watts, hp):
    translation = translations.get(language, translations['hebrew'])
    lifted_text = translation['lifted'].format(weight=weight, distance=distance)
    time_text = translation['time'].format(time=time)
    power_text = translation['power'].format(watts=watts, hp=hp)
    return lifted_text + time_text + power_text


def reset_display():
    """Reset display variables and reinitialize the screen layout."""
    global last_hp, last_try_max_hp, last_try_max_distance, last_try_max_time_diff, is_try_active
    print("Resetting display after 30 seconds")
    last_hp = 0
    last_try_max_hp = 0
    last_try_max_distance = 0
    last_try_max_time_diff = 0
    is_try_active = False
    setup_measuring_screen()


def update_measuring_screen(frame):
    """Update the display for each frame in the animation based on current horsepower."""
    global last_try_max_hp, last_try_max_distance, last_try_max_time_diff,\
          last_update_time, start_time, last_try_end_time

    current_time = time.time()

    # Check if Reset is Needed
    if last_try_end_time is not None and (current_time - last_try_end_time) > reset_duration:
        reset_display()
        last_try_end_time = None  # Reset the end time to indicate no active try
        return [img_display, hp_text]

    # Throttle Updates Based on update_interval
    if current_time - last_update_time < update_interval:
        return [img_display, hp_text]  # Skip this update to avoid too frequent rendering

    last_update_time = current_time  # Update the time for the next frame

    if hp_data_generator:
        hp = next(hp_data_generator)
    else:
        hp = 0  # No serial data available, so default to 0 HP
    # hp = next(hp_data_generator)

    # Track Try Start Time        
    if is_try_active and start_time is None:
        start_time = current_time

    # Track Try End Time
    if not is_try_active and start_time is not None:
        last_try_end_time = current_time
        start_time = None  # Reset start_time since the try ended

    # Calculate current_distance and Power Stats
    if last_try_max_distance > 0:
        current_distance = last_try_max_distance / 10
    else:
        current_distance = 0

    # Format current_distance to two decimal places

    watts = last_try_max_hp * WATTS_CONSTANT

    # Translate Text for Display
    translated_text = get_translated_text(
        current_language,  # This is the selected language
        weight=CURRENT_WEIGHT,
        distance=current_distance,
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

    # Update Image Based on HP and Redraw
    result_img = blend_images(last_try_max_hp)
    img_display.set_data(np.array(result_img))
    plt.draw()

    return [img_display, hp_text]



###### SETUP EXIT HANDLERS AND LOGGING ######

# Ensure serial connection is closed on exit
def close_serial_connection():
    if serial_connection and serial_connection.is_open:
        serial_connection.close()
    print("Serial connection closed.")

# Register the close_serial_connection function to run on exit
atexit.register(close_serial_connection)

# Listen for the window close event in matplotlib
def on_close(event):
    close_serial_connection()  # Close the serial connection
    sys.exit(0)  # Terminate the program

# Connect the close event handler to the figure
fig.canvas.mpl_connect('close_event', on_close)

# Configure logging
logging.basicConfig(
    filename="error_log.txt",  # File to save error log
    level=logging.ERROR,       # Log level set to capture errors
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log_exception(exc_type, exc_value, exc_traceback):
    """Log uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Skip logging for keyboard interrupts
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Log the exception with traceback
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

# Set the custom exception hook
sys.excepthook = log_exception


###### MAIN FUNCTION ######

# Main function or main code
def main():
    try:
        # Your main code here
        # For example, if you have the `setup_measuring_screen()` function and other code:
        setup_measuring_screen()
        plt.show()

    except Exception as e:
        # Log any other exceptions that may not be caught
        logging.error("Exception occurred in the main loop", exc_info=True)
        # Print to console for debugging purposes (optional)
        print("An error occurred. Check error_log.txt for details.")
        raise  # Optionally, re-raise the exception if needed

if __name__ == "__main__":
    main()