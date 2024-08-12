from PIL import Image, ImageDraw
import numpy as np

# Load the images
empty_image_path = '/Users/dolevsmac/Desktop/SciMuse project/horsepower project/horse ilus/empty.png'
full_image_path = '/Users/dolevsmac/Desktop/SciMuse project/horsepower project/horse ilus/yellow.png'

empty_img = Image.open(empty_image_path).convert("RGBA")
full_img = Image.open(full_image_path).convert("RGBA")

# Ensure the images are the same size
empty_img = empty_img.resize(full_img.size)

# Function to blend images based on horsepower value
def blend_images(horsepower, min_hp=0, max_hp=100):
    # Normalize the horsepower value
    normalized_hp = (horsepower - min_hp) / (max_hp - min_hp)
    normalized_hp = np.clip(normalized_hp, 0, 1)  # Ensure it stays within [0, 1]
    
    # Create a mask based on the normalized horsepower
    mask = Image.new("L", empty_img.size, 0)  # "L" mode for grayscale (mask)
    draw = ImageDraw.Draw(mask)
    
    # Calculate the fill height
    width, height = full_img.size
    fill_height = int(normalized_hp * height)
    
    # Draw the filled rectangle from the bottom up
    draw.rectangle([0, height - fill_height, width, height], fill=255)
    
    # Composite the images using the mask
    result_img = Image.composite(full_img, empty_img, mask)
    
    return result_img
