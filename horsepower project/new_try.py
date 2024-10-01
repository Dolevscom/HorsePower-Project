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
# CURRENT_WEIGHT = 1.525   # Weight of the object in kg 
# CURRENT_WEIGHT = 4.519  # Weight of the object in kg 
CURRENT_WEIGHT = 6  # Weight of the object in kg 
STARTING_DISTNACE = 1160

MIN_HP = 0 
MAX_HP = 0.01 
DISTANCE_CHANGE_THRESHOLD = 30 
WATTS_CONSTANT = 745.7 

######################### ***SHOULD BE CHANGED BETWEEN DIFFERENT COMPUTERS*** #########################
ARDUINO_PORT = 'COM5' 
# Load local files 
heading  = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\top.jpg'
empty_image_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\empty1.jpg'
full_image_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\full2.jpg'
gif_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\opening.gif'
font_path = r'C:\Users\Motorola\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf'
######################### ***Thats it*** ######################### 


# loading assets
center_img  = Image.open(heading).convert("RGBA") 
empty_img = Image.open(empty_image_path).convert("RGBA") 
full_img = Image.open(full_image_path).convert("RGBA") 
empty_img = empty_img.resize(full_img.size) # Ensure the images are the same size 
gif_frames = [frame.copy() for frame in ImageSequence.Iterator(Image.open(gif_path))] 
width, height = full_img.size 
aspect_ratio = width / height 
custom_font = fm.FontProperties(fname=font_path)

##### GLOBALS ###### 
last_hp = 0  # Global variable to store the last horsepower value 
is_try_active = False  # To track if a "try" is ongoing 
highest_hp_in_try = 0  # To store the highest horsepower during a "try" 
last_try_max_hp = 0  # To store the max horsepower of the last try 
last_try_max_distance = 0  # To store the distance of the last try's max horsepower
last_try_max_time_diff = 0  # To store the time difference of the last try's max horsepower
current_screen = 'opening' 
min_hp_observed = float('inf') 
max_hp_observed = float('-inf') 
ani_measuring = None 


# Set up the serial connection with the Arduino 
try: 
    serial_connection = serial.Serial(ARDUINO_PORT, 115200, timeout=1) 
except serial.SerialException as e: 
    print(f"Error opening serial port: {e}") 


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
    global last_hp, is_try_active, highest_hp_in_try, min_hp_observed,\
          max_hp_observed, last_try_max_hp, last_try_max_time_diff, last_try_max_distance
 
    print("Starting data generator...")  # Debugging print 
 
    while True: 
        try: 
            if serial_connection.in_waiting > 0:  # Check if there's data to read 
                # Read all available data from the serial buffer 
                raw_data = serial_connection.read(serial_connection.in_waiting).decode('utf-8').strip() 
     
                # Split the data by newlines to get each distance reading separately 
                data_lines = raw_data.splitlines() 
                # print(f"Received data: {data_lines}")  # Debugging print to see raw sensor data 
                 
                current_time = time.time() 
                for line in data_lines: 
                    try: 
                        current_distance = float(line.strip())  # Convert the line to a float 
                    except ValueError as e: 
                        # print(f"ValueError: {e} - Received invalid data: {line}") 
                        continue 
 
                if last_distance is not None: 
                    time_diff = max(current_time - last_time, 0.001) if last_time else 1 
                     
                    # If the distance change exceeds the threshold, calculate horsepower 
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
                        # print(f"Calculated Horsepower: {hp:.4f}")  # Debugging print 
                        yield hp
                    else: 
                        if is_try_active: 
                            is_try_active = False 
                            last_try_max_hp = highest_hp_in_try  # Save the max HP of the last try
                            
                            # Calculate the total duration of the try
                            last_try_max_time_diff  = current_time - try_start_time if try_start_time else 0
                            last_try_max_distance = abs(current_distance - last_distance)
                            
                            # Reset the start time after the try ends
                            try_start_time = None
                            
                            yield 0  # Yield with the total duration of the try
                        else: 
                            yield 0  # No significant change, yield 0 horsepower 
 
                last_distance = current_distance 
                last_time = current_time 
 
        except ValueError as e: 
            print(f"ValueError: {e}")  # Handle and print any conversion errors 
            continue
 
##### PLOTTING ###### 
 
hp_data_generator = infinite_data_generator(serial_connection) 
fig, ax = plt.subplots(figsize=(8, 8/aspect_ratio)) 
ax.axis('off') 
img_display = ax.imshow(np.zeros((height, width, 4), dtype=np.uint8)) 
hp_text = ax.text(0.5, 0.9, '', ha='center', va='center', fontsize=30, fontweight='bold', color='black', 
                  bbox=dict(facecolor='lightgray', edgecolor='black', boxstyle='round,pad=0.5')) 
 
fig.patch.set_visible(False)

##### SETUP AND UPDATE SCREENS ###### 
 
def on_click(event):
    global current_screen, ani_opening

    print(f"Screen Clicked - Current Screen: {current_screen}")  # Debugging print

    if current_screen == 'opening':
        current_screen = 'measuring'
        ani_opening.event_source.stop()  # Stop the opening animation
        ax.cla()  # Clear the content of the current axes, but keep the figure
        setup_measuring_screen()
        plt.draw()  # Redraw the figure

def update_opening_screen(frame): 
    ax.cla()  # Clear the axes
    ax.axis('off') 
    ax.imshow(gif_frames[frame % len(gif_frames)]) 
    return [ax] 

def setup_measuring_screen():
    global img_display, hp_text, ani_measuring

    print("Setting up measuring screen...")  # Debugging print
    fig.clear()
    gs = GridSpec(3, 1, height_ratios=[3, 1, 3])  # Define 3 rows with different height ratios
    
    # Top image (center image)
    ax1 = fig.add_subplot(gs[0])
    ax1.imshow(center_img)
    ax1.axis('off')

    # Middle section for the text
    ax2 = fig.add_subplot(gs[1])
    hebrew_text = ''  # Add any initial text or leave empty
    reshaped_text = arabic_reshaper.reshape(hebrew_text)
    bidi_text = get_display(reshaped_text)
    
    hp_text = ax2.text(0.95, 0.55, bidi_text, ha='right', va='center', fontsize=15,
                      fontproperties=custom_font, color='black', fontweight='bold',
                      transform=ax.transAxes, zorder=2,
                      bbox=dict(facecolor='white', alpha=0.8, edgecolor='none'))
    ax2.axis('off')

    # Bottom section for the full/empty images
    ax3 = fig.add_subplot(gs[2])
    img_display = ax3.imshow(np.zeros((height, width, 4), dtype=np.uint8))  # Placeholder for empty/full images
    ax3.axis('off')
  
    # Adjust the spacing to remove margins
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0, hspace=0, wspace=0)
    plt.tight_layout(pad=0, h_pad=0, w_pad=0)

    fig.patch.set_visible(False)  # Turn off the figure background

    ani_measuring = animation.FuncAnimation(fig, update_measuring_screen, frames=100, interval=200, blit=False)
    plt.draw()  # Redraw the figure

def update_measuring_screen(frame):
    global min_hp_observed, max_hp_observed, last_hp, last_try_max_hp, last_try_max_distance, last_try_max_time_diff


    # Retrieve the next horsepower value and related data
    hp = next(hp_data_generator)
    distance_in_cm = (STARTING_DISTNACE - last_try_max_distance) / 100

    if hp == 0:
        result_img = blend_images(0)  # Display zero horsepower image
    else:
        min_hp_observed = min(min_hp_observed, hp)
        max_hp_observed = max(max_hp_observed, hp)
        result_img = blend_images(hp)  # Update image with the new horsepower value

    hebrew_text = f'הרמתם {CURRENT_WEIGHT} ק"ג לגובה {distance_in_cm:.3f} ס"מ'\
                    f'\nתוך {last_try_max_time_diff:.3f} שניות \n'\
                        f'ההספק שהפקתם מגופכם הוא {(last_try_max_hp * WATTS_CONSTANT):.3f} וואט \n'\
                            f'שהם {last_try_max_hp:.3f} כח סוס'
    
    # Update the Hebrew text dynamically
    reshaped_text = arabic_reshaper.reshape(hebrew_text)
    bidi_text = get_display(reshaped_text)
    hp_text.set_text(bidi_text)

    # Update the displayed image with the blended result image
    img_display.set_data(np.array(result_img))

    return [img_display, hp_text]


# Initial animation for the opening screen 
ani_opening = animation.FuncAnimation(fig, update_opening_screen, frames=len(gif_frames), interval=200, repeat=True) 
fig.canvas.mpl_connect('button_press_event', on_click) 

print("Showing initial screen...")  # Debugging print 
plt.show()


