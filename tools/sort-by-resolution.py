import os
import re
import shutil
from PIL import Image
from moviepy.editor import VideoFileClip

def get_resolution(filename):
    # Function to get resolution of an image or video file
    if is_image(filename):
        return get_resolution_image(filename)
    elif is_video(filename):
        return get_resolution_video(filename)
    else:
        return None

def is_image(filename):
    # Check if the file has an image extension
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff']
    _, file_ext = os.path.splitext(filename.lower())
    return file_ext in image_extensions

def is_video(filename):
    # Check if the file has a video extension
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
    _, file_ext = os.path.splitext(filename.lower())
    return file_ext in video_extensions

def get_resolution_image(filename):
    # Function to get resolution of an image using PIL (Pillow)
    try:
        with Image.open(filename) as img:
            width, height = img.size
            return f"{width}x{height}"
    except Exception as e:
        print(f"Failed to get resolution for {filename}: {str(e)}")
        return None

def get_resolution_video(filename):
    # Function to get resolution of a video using moviepy
    try:
        clip = VideoFileClip(filename)
        width = clip.size[0]
        height = clip.size[1]
        clip.close()
        return f"{width}x{height}"
    except Exception as e:
        print(f"Failed to get resolution for {filename}: {str(e)}")
        return None

def organize_files(directory):
    # Create a dictionary to hold resolution folders
    resolution_folders = {}
    
    # Iterate through each file in the directory
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        
        # Check if it's a file
        if os.path.isfile(file_path):
            # Determine the resolution of the file
            resolution = get_resolution(file_path)
            
            if resolution:
                # Create resolution-specific folder if it doesn't exist
                if resolution not in resolution_folders:
                    resolution_folder = os.path.join(directory, resolution)
                    os.makedirs(resolution_folder, exist_ok=True)
                    resolution_folders[resolution] = resolution_folder
                
                # Move the file to the resolution-specific folder
                try:
                    shutil.move(file_path, os.path.join(resolution_folders[resolution], filename))
                    print(f"Moved {filename} to {resolution_folders[resolution]}")
                except Exception as e:
                    print(f"Failed to move {filename}: {str(e)}")

if __name__ == "__main__":
    # Prompt user to input directory
    input_directory = input("Enter the directory: ").strip()
    
    # Validate directory existence
    if os.path.exists(input_directory) and os.path.isdir(input_directory):
        organize_files(input_directory)
        print("Files organized successfully.")
    else:
        print("Directory not found or invalid.")
