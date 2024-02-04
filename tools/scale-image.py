import os
from PIL import Image

class ImageScaler:
    @staticmethod
    def scale_image(input_path, output_path, width=None, height=None, mode='fit'):
        """
        Scale an image with various preservation modes.
        
        Args:
        input_path (str): Path to the input image
        output_path (str): Path to save the scaled image
        width (int, optional): Desired width
        height (int, optional): Desired height
        mode (str): Scaling mode - 'fit', 'fill', 'crop', or 'stretch'
        """
        try:
            # Open the image
            with Image.open(input_path) as img:
                # Get original image dimensions
                orig_width, orig_height = img.size
                orig_ratio = orig_width / orig_height

                # Determine scaling mode
                if mode == 'fit':
                    # Resize to fit within specified dimensions while maintaining aspect ratio
                    if width and height:
                        # Calculate scaling to fit within both width and height
                        scale_w = width / orig_width
                        scale_h = height / orig_height
                        scale = min(scale_w, scale_h)
                        new_width = int(orig_width * scale)
                        new_height = int(orig_height * scale)
                    elif width:
                        new_width = width
                        new_height = int(width / orig_ratio)
                    elif height:
                        new_height = height
                        new_width = int(height * orig_ratio)
                    else:
                        raise ValueError("Either width or height must be specified")
                    
                    scaled_img = img.resize((new_width, new_height), Image.LANCZOS)

                elif mode == 'fill':
                    # Resize to fill dimensions, possibly cropping
                    if not (width and height):
                        raise ValueError("Both width and height must be specified for 'fill' mode")
                    
                    # Calculate scale to cover both dimensions
                    scale_w = width / orig_width
                    scale_h = height / orig_height
                    scale = max(scale_w, scale_h)
                    
                    # Resize image
                    new_width = int(orig_width * scale)
                    new_height = int(orig_height * scale)
                    scaled_img = img.resize((new_width, new_height), Image.LANCZOS)
                    
                    # Crop to exact dimensions
                    left = (new_width - width) // 2
                    top = (new_height - height) // 2
                    scaled_img = scaled_img.crop((
                        left, 
                        top, 
                        left + width, 
                        top + height
                    ))

                elif mode == 'crop':
                    # Resize and crop from center
                    if not (width and height):
                        raise ValueError("Both width and height must be specified for 'crop' mode")
                    
                    # Resize to smallest dimension
                    if orig_width > orig_height:
                        resize_height = height
                        resize_width = int(orig_width * (height / orig_height))
                    else:
                        resize_width = width
                        resize_height = int(orig_height * (width / orig_width))
                    
                    # Resize
                    scaled_img = img.resize((resize_width, resize_height), Image.LANCZOS)
                    
                    # Crop from center
                    left = (resize_width - width) // 2
                    top = (resize_height - height) // 2
                    scaled_img = scaled_img.crop((
                        left, 
                        top, 
                        left + width, 
                        top + height
                    ))

                elif mode == 'stretch':
                    # Forcefully stretch image to exact dimensions
                    if not (width and height):
                        raise ValueError("Both width and height must be specified for 'stretch' mode")
                    
                    scaled_img = img.resize((width, height), Image.LANCZOS)

                else:
                    raise ValueError("Invalid mode. Choose 'fit', 'fill', 'crop', or 'stretch'")

                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Save the scaled image
                scaled_img.save(output_path)
                print(f"Image successfully scaled and saved to {output_path}")
                print(f"New dimensions: {scaled_img.size[0]} x {scaled_img.size[1]}")
                
                return scaled_img.size

        except FileNotFoundError:
            print(f"Error: File not found at {input_path}")
        except PermissionError:
            print(f"Error: Permission denied when trying to save to {output_path}")
        except Image.UnidentifiedImageError:
            print(f"Error: Unable to identify image file {input_path}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

def main():
    # Get input image path from user
    input_path = input("Enter the full path to the image you want to scale: ").strip()
    
    # Check if file exists
    if not os.path.isfile(input_path):
        print("Error: File does not exist.")
        return
    
    # Open image to display current dimensions
    with Image.open(input_path) as img:
        original_width, original_height = img.size
        print(f"Original image dimensions: {original_width} x {original_height}")
    
    # Get scaling mode
    while True:
        print("\nScaling Modes:")
        print("1. Fit - Resize to fit within dimensions (no stretching)")
        print("2. Fill - Cover entire area, potentially cropping")
        print("3. Crop - Resize and crop from center")
        print("4. Stretch - Force image to exact dimensions (may distort)")
        
        mode_choice = input("Choose scaling mode (1/2/3/4): ").strip()
        mode_map = {'1': 'fit', '2': 'fill', '3': 'crop', '4': 'stretch'}
        
        if mode_choice in mode_map:
            mode = mode_map[mode_choice]
            break
        else:
            print("Invalid choice. Please try again.")
    
    # Get new dimensions
    while True:
        try:
            if mode == 'fit':
                print("\nEnter at least one dimension (width or height)")
                width_input = input("Enter width (or press Enter to skip): ").strip()
                height_input = input("Enter height (or press Enter to skip): ").strip()
                
                width = int(width_input) if width_input else None
                height = int(height_input) if height_input else None
                
                if not (width or height):
                    print("Error: You must specify at least one dimension.")
                    continue
            else:
                width = int(input("Enter the new width: "))
                height = int(input("Enter the new height: "))
            
            # Validate dimensions
            if width is not None and width <= 0:
                print("Error: Width must be a positive number.")
                continue
            if height is not None and height <= 0:
                print("Error: Height must be a positive number.")
                continue
            
            break
        except ValueError:
            print("Error: Please enter valid integer dimensions.")
    
    # Automatically create output path in a 'scaled' subdirectory
    input_dir = os.path.dirname(input_path)
    scaled_dir = os.path.join(input_dir, 'Scaled')
    
    # Create scaled directory if it doesn't exist
    os.makedirs(scaled_dir, exist_ok=True)
    
    # Generate output filename
    input_filename = os.path.basename(input_path)
    filename_base, ext = os.path.splitext(input_filename)
    
    # Create output filename with mode and dimensions
    if mode == 'fit':
        output_filename = f"{filename_base}_fit_{width or 'auto'}x{height or 'auto'}{ext}"
    else:
        output_filename = f"{filename_base}_{mode}_{width}x{height}{ext}"
    
    output_path = os.path.join(scaled_dir, output_filename)
    
    # Scale the image
    ImageScaler.scale_image(input_path, output_path, width, height, mode)
    
    print("Image scaling script completed.")

if __name__ == "__main__":
    main()
