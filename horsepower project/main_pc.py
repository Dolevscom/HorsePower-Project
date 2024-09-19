import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from PIL import Image, ImageDraw, ImageSequence
import numpy as np
from bidi.algorithm import get_display  # Add this for bidi support
import arabic_reshaper  # Add this for reshaping Hebrew text
import threading

###### CONSTANTS ######
CURRENT_WEIGHT = 1.525  # Weight of the object in kg
MIN_HP = 0
MAX_HP = 100
DISTANCE_CHANGE_THRESHOLD = 30
last_hp = 0
is_try_active = False
highest_hp_in_try = 0
last_try_max_hp = 0
serial_connection = None
# Load the images
empty_image_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\horse ilus\empty.png'
full_image_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\horse ilus\yellow.png'
gif_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\animation.gif'

empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")
empty_img = empty_img.resize(full_img.size)

# Load GIF
gif_frames = [frame.copy() for frame in ImageSequence.Iterator(Image.open(gif_path))]

###### HELPER FUNCTIONS ######

def calculate_horsepower(speed_mps):
    hp = (CURRENT_WEIGHT * speed_mps) / 745.7
    print(f"Calculated Horsepower: {hp:.4f}")  # Debugging print
    return hp


def blend_images(horsepower, min_hp=MIN_HP, max_hp=MAX_HP):
    # print(f"Blending images with horsepower: {horsepower:.4f}, min_hp: {min_hp}, max_hp: {max_hp}")  # Debugging print

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
    fill_width = int(normalized_hp * width)
    draw.rectangle([width - fill_width, 0, width, height], fill=255)
    
    result_img = Image.composite(full_img, empty_img, mask)
    return result_img

###### MAIN CODE ######

# Generator to read range data from the serial port

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

                    if is_try_active:
                        if hp > highest_hp_in_try:
                            highest_hp_in_try = hp
                    else:
                        is_try_active = True  # Start a new try
                        highest_hp_in_try = hp  # Initialize with the current horsepower

                    last_hp = hp
                    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}, "
                          f"Data: {current_distance}, Speed: {speed_mps:.2f} m/s, Horsepower: {hp:.4f}, weight: {CURRENT_WEIGHT} kg")
                    
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


# PLOTTING ######
hp_data_generator = infinite_data_generator(serial_connection)

fig, ax = plt.subplots()

# Remove axes to ensure no plot is displayed
ax.axis('off')

# Track which screen is active
current_screen = 'opening'

# Min and max observed horsepower values
min_hp_observed = float('inf')
max_hp_observed = float('-inf')

# Serial connection is delayed until after the opening screen
serial_connection = None

def on_click(event):
    global current_screen, serial_connection, hp_data_generator

    print(f"Screen Clicked - Current Screen: {current_screen}")  # Debugging print
    
    if current_screen == 'opening':
        # Try to establish a serial connection
        try:
            print("Attempting to establish serial connection...")  # Debugging print
            serial_connection = serial.Serial('COM3', 115200, timeout=1)
            hp_data_generator = infinite_data_generator(serial_connection)
            print("Serial connection established.")  # Debugging print
        except serial.SerialException as e:
            print(f"SerialException: {e}")  # Debugging print
            return  # Do not proceed if connection fails

        # Switch to measuring screen on mouse click
        current_screen = 'measuring'
        plt.clf()
        setup_measuring_screen()
        plt.show()


def update_opening_screen(frame):
    ax.clear()
    ax.axis('off')

    # Display the GIF
    ax.imshow(gif_frames[frame % len(gif_frames)])

    hebrew_text = 'הרימו את המשקולת'
    reshaped_text = arabic_reshaper.reshape(hebrew_text)
    bidi_text = get_display(reshaped_text)

    ax.text(0.5, 1, bidi_text, fontsize=30, ha='center', va='top', color='black', family='David', fontweight='bold', transform=ax.transAxes)
    
    return [ax]

def setup_measuring_screen():
    global img_display, hp_text

    print("Setting up measuring screen...")  # Debugging print
    
    # Create figure with two subplots: one for the image and one for the text
    fig, (ax_img, ax_text) = plt.subplots(1, 2, figsize=(10, 5))

    # Hide the axes for both subplots
    ax_img.axis('off')  # Hide axes for the image
    ax_text.axis('off')  # Hide axes for the text

    # Debugging: print the image dimensions
    print(f"Empty image dimensions: {empty_img.size}")

    # Initialize the image display with a placeholder (empty black image)
    img_display = ax_img.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))

    # Reshape and prepare Hebrew text using BiDi and arabic_reshaper
    hebrew_text = 'כח סוס'
    reshaped_text = arabic_reshaper.reshape(hebrew_text)
    bidi_text = get_display(reshaped_text)

    # Add the reshaped Hebrew text in the second subplot
    hp_text = ax_text.text(0.5, 0.5, bidi_text, ha='center', va='center', fontsize=30, color='black', fontweight='bold')

    # Debugging: confirm text initialization
    print("Text initialized on measuring screen.")

    # Start the animation for the measuring screen
    ani_measuring = animation.FuncAnimation(fig, update_measuring_screen, frames=100, interval=100, blit=False)

    # Ensure proper layout
    plt.tight_layout()

    # Debugging: confirm that the animation has started
    print("Animation started for measuring screen.")

    plt.show()




def update_measuring_screen(frame):
    global min_hp_observed, max_hp_observed, last_hp, highest_hp_in_try, last_try_max_hp
    
    hp = next(hp_data_generator)
    print(f"Updating screen - HP: {hp:.4f}")  # Debugging print

    if hp == 0:
        result_img = blend_images(0, min_hp=min_hp_observed, max_hp=max_hp_observed)
        hp_text.set_text(f'כח סוס : 0.0000\nניסיון אחרון: {last_try_max_hp:.4f}\nמקסימום: {max_hp_observed:.4f}')
        print(f"Text updated for 0 HP.")  # Debugging print
    else:
        min_hp_observed = min(min_hp_observed, hp)
        max_hp_observed = max(max_hp_observed, hp)
        result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
        hp_text.set_text(f'כח סוס: {hp:.4f}\nניסיון אחרון: {last_try_max_hp:.4f}\nמקסימום: {max_hp_observed:.4f}')
        print(f"Text updated for HP: {hp:.4f}")  # Debugging print

    img_display.set_data(np.array(result_img))
    return [img_display, hp_text]



