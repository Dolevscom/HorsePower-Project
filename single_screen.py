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
DISTANCE_CHANGE_THRESHOLD = 100  # Threshold to detect significant distance changes
WATTS_CONSTANT = 745.7  # Constant for horsepower to watts conversion
WEIGHT_TO_FORCE_CONST = 9.81  # Gravity constant to convert weight to force
METER_TO_FEET_CONST = 3.28084  # Conversion constant from meters to feet
SECONDS_TO_MINUTE = 60  # Conversion from seconds to minutes
INITIAL_STAGE = 600

####### [computer in the display] ########

ARDUINO_PORT = '/dev/ttyUSB0'

# Load local files
empty_image_path = r'/home/mada/Desktop/HorsePower-Project/horsepower project/assets/Empty horse.jpg'
full_image_path = r'/home/mada/Desktop/HorsePower-Project/horsepower project/assets/Full horse.jpg'

# Font paths for different languages
font_paths = {
    'hebrew': r'/home/mada/Desktop/HorsePower-Project/horsepower project/assets/fonts/SimplerPro_HLAR-Semibold.otf',
    'english': r'/home/mada/Desktop/HorsePower-Project/horsepower project/assets/fonts/SimplerPro_HLAR-Semibold.otf',
    'arabic': r'/home/mada/Desktop/HorsePower-Project/horsepower project/assets/fonts/NotoKufiArabic-SemiBold.ttf'  # Use a font that supports Arabic
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


secondary_headline_text = {
    'hebrew': 'הרימו את המשקולת במהירות האפשרית',
    'english': 'Lift the weight as fast as possible',
    'arabic': 'ارفع الوزن بأسرع ما يمكن'
}


# List of available languages
languages = ['hebrew', 'english', 'arabic']
current_language_index = 0  # Start with Hebrew
current_language = languages[current_language_index]  # Initial language is Hebrew


# Load assets
empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")
empty_img = empty_img.resize(full_img.size)  # Ensure the images are the same size
# gif_frames = [frame.copy() for frame in ImageSequence.Iterator(Image.open(gif_path))]
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
    logging.error(f"Error opening serial port: {e}")
    serial_connection = None  # Set to None if serial connection fails


###### HELPER FUNCTIONS ######


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
                    logging.info(f"Language switched to: {current_language}")
                    setup_measuring_screen()
                    plt.draw()
                    continue  # Skip further processing for this loop iteration

                try:
                    # Convert line to float and add to smoothing buffer
                    current_distance = float(line.strip())
                    distance_buffer.append(current_distance)  # Add to smoothing buffer
                    smoothed_distance = sum(distance_buffer) / len(distance_buffer)  # Smoothed distance
                    logging.info(f"Raw Distance: {current_distance} mm, Smoothed Distance: {smoothed_distance:.1f} mm")

                    # Initialize `last_distance` for the first iteration
                    if last_distance is None:
                        last_distance = smoothed_distance
                        last_time = current_time
                        continue

                    # Calculate time difference
                    time_diff = max(current_time - last_time, 0.001)

                    # Skip if the time difference is too small
                    if time_diff < 0.05:
                        logging.debug("Skipping: Time difference too small for processing.")
                        continue

                    # Calculate distance moved in meters
                    distance_moved_meters = abs(smoothed_distance - last_distance) / 1000  # Convert mm to meters

                    # Check if movement exceeds threshold
                    if distance_moved_meters > (DISTANCE_CHANGE_THRESHOLD / 1000):
                        # Calculate horsepower
                        hp = calculate_horsepower(distance_moved_meters, time_diff)
                        logging.info(f"Distance Moved: {distance_moved_meters:.3f} meters, HP: {hp:.2f}")

                        if is_try_active:
                            # Update closest distance in this try
                            if smoothed_distance < closest_distance_in_try:
                                closest_distance_in_try = smoothed_distance

                            # Track the maximum horsepower
                            if hp > highest_hp_in_try:
                                highest_hp_in_try = hp
                                # logging.info(f"New Highest HP in Try: {highest_hp_in_try:.2f}")
                        else:
                            # Start a new try
                            is_try_active = True
                            try_start_time = current_time
                            closest_distance_in_try = smoothed_distance
                            highest_hp_in_try = hp
                            # logging.info(f"New Try Started. Initial HP: {hp:.2f}")

                        last_hp = hp
                        yield hp
                    else:
                        # logging.debug("Skipping: Movement below threshold.")
                        if is_try_active:
                            # End the try
                            is_try_active = False
                            last_try_max_hp = highest_hp_in_try
                            last_try_max_time_diff = current_time - try_start_time if try_start_time else 0
                            last_try_max_distance = STARTING_DISTANCE - closest_distance_in_try - INITIAL_STAGE
                            # logging.info(
                                # f"Try Ended. Max HP: {last_try_max_hp:.2f}, Max Distance: {last_try_max_distance:.2f} mm, "
                                # f"Duration: {last_try_max_time_diff:.2f} seconds")
                            try_start_time = None
                            yield 0
                        else:
                            yield 0
                except ValueError:
                    logging.error(f"Invalid data received: {line.strip()}")
                    continue

                # Update last_distance and last_time
                last_distance = smoothed_distance
                last_time = current_time



##### DISPLAY ######

def open_full_screen():
    """Display figure in full screen on Linux."""
    fig, ax = plt.subplots(figsize=(8, 8))  # Create a figure and axis
    ax.axis('off')  # Turn off axis

    # Move the figure to full screen
    backend = plt.get_backend()
    mng = plt.get_current_fig_manager()

    if backend == 'TkAgg':
        print("Using TkAgg backend for full screen on Linux")
        mng.window.attributes('-fullscreen', True)  # TkAgg: Make full screen
    elif backend in ['Qt5Agg', 'QtAgg']:
        print("Using QtAgg backend for full screen on Linux.")
        mng.window.showFullScreen()  # QtAgg: Full-screen display
    else:
        print(f"Using unsupported backend: {backend}. Full screen may not work.")

    return fig, ax


# Initialize data generator
hp_data_generator = infinite_data_generator(serial_connection) if serial_connection else None
fig, ax = open_full_screen()
img_display = ax.imshow(np.zeros((height, width, 4), dtype=np.uint8))
fig.canvas.manager.toolbar.pack_forget()



##### SETUP AND UPDATE SCREENS ######



def setup_measuring_screen():
    """Initialize the layout for the measuring screen with sections for heading, text, and image."""
    global img_display, hp_text, ani_measuring

    # Clear the figure and define the layout
    fig.clear()
    gs = GridSpec(3, 1, height_ratios=[2.5, 1, 3])  # Adjust height ratios

    # Top section for the main and secondary headlines
    ax1 = fig.add_subplot(gs[0])
    ax1.axis('off')  # Turn off the axis for a clean look

    # Main headline
    main_heading = heading_text[current_language]
    reshaped_main = arabic_reshaper.reshape(main_heading) if current_language in ['arabic', 'hebrew'] else main_heading
    bidi_main = get_display(reshaped_main) if current_language in ['arabic', 'hebrew'] else reshaped_main
    ax1.text(
        0.5, 0.7,  # Adjust position (closer to the center of this subplot)
        bidi_main,
        ha='center', va='center', fontsize=80,
        fontproperties=fm.FontProperties(fname=font_paths[current_language]),
        fontweight='bold', color='black'
    )

    # Secondary headline
    secondary_heading = secondary_headline_text[current_language]
    reshaped_secondary = arabic_reshaper.reshape(secondary_heading) if current_language in ['arabic', 'hebrew'] else secondary_heading
    bidi_secondary = get_display(reshaped_secondary) if current_language in ['arabic', 'hebrew'] else reshaped_secondary
    ax1.text(
        0.5, 0.5,  # Slightly below the main headline
        bidi_secondary,
        ha='center', va='center', fontsize=40,  # Smaller font size
        fontproperties=fm.FontProperties(fname=font_paths[current_language]),
        fontweight='regular', color='gray'
    )

    # Section for the text
    ax2 = fig.add_subplot(gs[1])
    hp_text = ax2.text(
        0.95, 0.95, '', ha='right', va='center', fontsize=30,
        fontproperties=fm.FontProperties(fname=font_paths[current_language]),
        color='black', fontweight='regular', transform=ax2.transAxes, zorder=2,
        bbox=dict(facecolor='white', alpha=0.8, edgecolor='none')
    )
    ax2.axis('off')

    # Bottom section for the full/empty images
    ax3 = fig.add_subplot(gs[2])
    img_display = ax3.imshow(np.zeros((height, width, 4), dtype=np.uint8))  # Placeholder for empty/full images
    ax3.axis('off')

    # Adjust layout
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0, hspace=0, wspace=0)
    plt.tight_layout(pad=0, h_pad=0, w_pad=0)
    fig.patch.set_visible(False)

    # Create animation, avoid re-creating if already exists
    if ani_measuring is None:
        ani_measuring = animation.FuncAnimation(
            fig, update_measuring_screen, frames=100, interval=200, blit=False
        )

    plt.draw()  # Redraw the figure



###### EVENT HANDLING AND DISPLAY UPDATE ######

# Function to change language based on spacebar press
def change_language_on_key(event):
    """Change display language when spacebar is pressed."""
    global current_language, current_language_index
   
    if event.key == ' ':
        current_language_index = (current_language_index + 1) % len(languages)
        current_language = languages[current_language_index]       
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
    logging.debug("Resetting display after 30 seconds")
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
        logging.info(f"Received new horsepower value: {hp:.2f}")
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
    logging.info(f"Max Distance: {current_distance:.2f} cm, Watts: {watts:.2f}, HP: {last_try_max_hp:.2f}")

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
    logging.debug("Image updated based on current horsepower.")
    plt.draw()

    return [img_display, hp_text]



###### SETUP EXIT HANDLERS AND LOGGING ######

def close_on_esc(event):
    """Exit fullscreen mode when the ESC key is pressed."""
    if event.key == 'escape':  # Check if the ESC key is pressed
        backend = plt.get_backend()
        mng = plt.get_current_fig_manager()

        if backend == 'TkAgg':
            # Exit fullscreen for TkAgg backend
            mng.window.attributes('-fullscreen', False)
            print("Exited fullscreen mode.")
        elif backend in ['Qt5Agg', 'QtAgg']:
            # Exit fullscreen for Qt-based backends
            mng.window.showNormal()
            logging.debug("Exited fullscreen mode.")
        else:
            print(f"Exiting fullscreen not supported for backend: {backend}")


# Connect the function to the key press event
fig.canvas.mpl_connect('key_press_event', close_on_esc)

# Ensure serial connection is closed on exit
def close_serial_connection():
    if serial_connection and serial_connection.is_open:
        serial_connection.close()
    logging.info("Serial connection closed.")

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
    filename="/home/mada/Desktop/HorsePower.log",  # Name of the log file
    level=logging.DEBUG,      # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s"  # Log message format
)

# Redirect print statements to logging
class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message.strip():  # Ignore empty lines
            self.level(message.strip())

    def flush(self):  # Needed for Python logging compatibility
        pass


# Redirect stdout and stderr to logging
sys.stdout = LoggerWriter(logging.info)  # Redirect standard output to INFO log level
sys.stderr = LoggerWriter(logging.error) 
logging.info("This is a test message.")


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
    print(matplotlib.get_backend())
    logging.shutdown()



