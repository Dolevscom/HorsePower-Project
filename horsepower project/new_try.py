import serial
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import font_manager as fm
from PIL import Image, ImageDraw, ImageSequence
import numpy as np
from bidi.algorithm import get_display 
import arabic_reshaper  # reshaping Hebrew text

###### CONSTANTS ######
CURRENT_WEIGHT = 1.525   # Weight of the object in kg
# CURRENT_WEIGHT = 4.519  # Weight of the object in kg
# CURRENT_WEIGHT = 7  # Weight of the object in kg

MIN_HP = 0
MAX_HP = 100
DISTANCE_CHANGE_THRESHOLD = 30
last_hp = 0  # Global variable to store the last horsepower value
is_try_active = False  # To track if a "try" is ongoing
highest_hp_in_try = 0  # To store the highest horsepower during a "try"
last_try_max_hp = 0  # To store the max horsepower of the last try
current_screen = 'opening'

##### GLOBALS ######

# Set up the serial connection with the Arduino
serial_connection = serial.Serial('COM3', 115200, timeout=0)  # Set timeout to 1 second

min_hp_observed = float('inf')
max_hp_observed = float('-inf')
ani_measuring = None

# Load the images (update paths for Windows)
empty_image_path = 'C:\\Users\\MakeMada\\Downloads\\HorsePower-Project-main\\HorsePower-Project-main\\horsepower project\\horse ilus\\empty.png'
full_image_path = 'C:\\Users\\MakeMada\\Downloads\\HorsePower-Project-main\\HorsePower-Project-main\\horsepower project\\horse ilus\\yellow.png'
gif_path = 'C:\\Users\\MakeMada\\Desktop\\HP project\\HorsePower-Project\\horsepower project\\animation.gif'
empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")
empty_img = empty_img.resize(full_img.size) # Ensure the images are the same size
gif_frames = [frame.copy() for frame in ImageSequence.Iterator(Image.open(gif_path))]


# Fonts loading
font_path = r'C:\Users\MakeMada\Desktop\HP project\HorsePower-Project\horsepower project\assets\fonts\SimplerPro_HLAR-Semibold.otf'
custom_font = fm.FontProperties(fname=font_path)

###### HELPER FUNCTIONS ######

# Function to calculate horsepower from speed
def calculate_horsepower(speed_mps):
    return (CURRENT_WEIGHT * speed_mps) / 745.7

# Function to blend images based on horsepower value
def blend_images(horsepower, min_hp=MIN_HP, max_hp=MAX_HP):
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

def infinite_data_generator(serial_connection):
    last_distance = None
    last_time = time.time()
    global last_hp, is_try_active, highest_hp_in_try, min_hp_observed, max_hp_observed, last_try_max_hp

    print("Starting data generator...")  # Debugging print

    while True:
        try:
            if serial_connection.in_waiting > 0:  # Check if there's data to read
                # Read all available data from the serial buffer
                raw_data = serial_connection.read(serial_connection.in_waiting).decode('utf-8').strip()
    
                # Split the data by newlines to get each distance reading separately
                data_lines = raw_data.splitlines()
                print(f"Received data: {data_lines}")  # Debugging print to see raw sensor data
                
                current_time = time.time()
                for line in data_lines:
                    try:
                        current_distance = float(line.strip())  # Convert the line to a float
                        # Proceed with your calculations using current_distance
                        # Example: process_sensor_data(current_distance)
                    except ValueError as e:
                        print(f"ValueError: {e} - Received invalid data: {line}")
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
                            highest_hp_in_try = hp  # Initialize with the current horsepower

                        last_hp = hp
                        print(f"Calculated Horsepower: {hp:.4f}")  # Debugging print
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

        except ValueError as e:
            print(f"ValueError: {e}")  # Handle and print any conversion errors
            continue

##### PLOTTING ######

hp_data_generator = infinite_data_generator(serial_connection)
fig, ax = plt.subplots()
ax.axis('off')
img_display = ax.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))
hp_text = ax.text(0.5, 0.5, '', ha='center', va='center', fontsize=20, fontweight='bold', color='black')


##### SETUP AND UPDATE SCREENS ######

def on_click(event):
    global current_screen

    print(f"Screen Clicked - Current Screen: {current_screen}")  # Debugging print
    
    # if current_screen == 'opening':
    #     # Try to establish a serial connection
    #     try:
    #         print("Attempting to establish serial connection...")  # Debugging print
    #         serial_connection = serial.Serial('COM3', 115200, timeout=1)
    #         hp_data_generator = infinite_data_generator(serial_connection)
    #         print("Serial connection established.")  # Debugging print
    #     except serial.SerialException as e:
    #         print(f"SerialException: {e}")  # Debugging print
    #         return  # Do not proceed if connection fails

    # Switch to measuring screen on mouse click
    current_screen = 'measuring'
    plt.clf()
    setup_measuring_screen()
    plt.show()


def update_opening_screen(frame):
    ax.clear(), ax.axis('off')

    # Display the GIF
    ax.imshow(gif_frames[frame % len(gif_frames)])

    hebrew_text = 'הרימו את המשקולת'
    reshaped_text = arabic_reshaper.reshape(hebrew_text)
    bidi_text = get_display(reshaped_text)

    ax.text(0.5, 1, bidi_text, fontsize=30, ha='center', va='top', color='black', fontproperties=custom_font, fontweight='bold', transform=ax.transAxes)
    
    return [ax]


def setup_measuring_screen():
    global img_display, hp_text, ani_measuring 

    print("Setting up measuring screen...")  # Debugging print
    
    # Create figure with two subplots: one for the image and one for the text
    fig, (ax_img, ax_text) = plt.subplots(1, 2, figsize=(10, 5))

    ax_img.axis('off'), ax_text.axis('off')  # Hide axes for the text and image

    # Initialize the image display with a placeholder (empty black image)
    img_display = ax_img.imshow(np.zeros((empty_img.height, empty_img.width, 4), dtype=np.uint8))

    # prepare Hebrew text using BiDi and arabic_reshaper AND ADD IT
    hebrew_text = 'כח סוס'
    reshaped_text = arabic_reshaper.reshape(hebrew_text)
    bidi_text = get_display(reshaped_text)
    hp_text = ax_text.text(0.5, 0.5, bidi_text, ha='center', va='center', fontsize=30,
                            fontproperties=custom_font, color='black', fontweight='bold')

    # Start the animation for the measuring screen
    ani_measuring = animation.FuncAnimation(fig, update_measuring_screen, frames=100, interval=200, blit=False)

    # Ensure proper layout
    plt.tight_layout()
    plt.show()

def update_measuring_screen(frame):
    global min_hp_observed, max_hp_observed, last_hp, highest_hp_in_try, last_try_max_hp
    
    hp = next(hp_data_generator)
    print(f"Updating screen - HP: {hp:.4f}")  # Debugging print

    if hp == 0:
        result_img = blend_images(0, min_hp=min_hp_observed, max_hp=max_hp_observed)
        
        # Hebrew text for "Horsepower: 0.0000", "Last Try Max HP", and "Max HP"
        hebrew_text = f'כח סוס: 0.0000\nניסיון אחרון: {last_try_max_hp:.4f}\nמקסימום: {max_hp_observed:.4f}'
        
        # Reshape and reorder Hebrew text to display correctly
        reshaped_text = arabic_reshaper.reshape(hebrew_text)
        bidi_text = get_display(reshaped_text)
        
        # Update the text in the UI
        hp_text.set_text(bidi_text)
        # print(f"Text updated for 0 HP.")  # Debugging print

    else:
        min_hp_observed = min(min_hp_observed, hp)
        max_hp_observed = max(max_hp_observed, hp)
        result_img = blend_images(hp, min_hp=min_hp_observed, max_hp=max_hp_observed)
        
        # Hebrew text for the current HP values
        hebrew_text = f'כח סוס: {hp:.4f}\nניסיון אחרון: {last_try_max_hp:.4f}\nמקסימום: {max_hp_observed:.4f}'
        
        # Reshape and reorder Hebrew text to display correctly
        reshaped_text = arabic_reshaper.reshape(hebrew_text)
        bidi_text = get_display(reshaped_text)
        
        # Update the text in the UI
        hp_text.set_text(bidi_text)
        # print(f"Text updated for HP: {hp:.4f}")  # Debugging print

    frame_skip = 5  # Only update the image every 5 frames
    if frame % frame_skip == 0: 
        img_display.set_data(np.array(result_img))
    return [img_display, hp_text]

# Initial animation for the opening screen
ani_opening = animation.FuncAnimation(fig, update_opening_screen, frames=len(gif_frames), interval=50, repeat=True)
fig.canvas.mpl_connect('button_press_event', on_click)

print("Showing initial screen...")  # Debugging print
plt.show()
