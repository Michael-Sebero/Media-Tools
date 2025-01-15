import os
from PIL import Image, ImageChops

def remove_black_border(input_path, output_folder):
    img = Image.open(input_path)
    bg = Image.new(img.mode, img.size, img.getpixel((0,0)))
    diff = ImageChops.difference(img, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        img_cropped = img.crop(bbox)
        output_path = os.path.join(output_folder, os.path.basename(input_path))
        img_cropped.save(output_path)

def process_images_in_directory(directory):
    output_folder = os.path.join(directory, "Output")
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(directory):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            input_path = os.path.join(directory, filename)
            remove_black_border(input_path, output_folder)

directory = input("Enter the directory: ")
process_images_in_directory(directory)
