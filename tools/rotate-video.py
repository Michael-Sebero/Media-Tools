import os
import random
import string
import threading
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Union
from moviepy.editor import VideoFileClip
from moviepy.video.fx.all import rotate

# Dictionary mapping rotation choices to degrees
rotation_choices = {
    "1": 90,
    "2": 180,
    "3": 270
}

def verify_video_file(file_path: str) -> bool:
    """Verify if the file is a valid video file."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', file_path],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception:
        return False

def reencode_video(input_file: str, temp_dir: str) -> Optional[str]:
    """Re-encode the video to ensure proper format and metadata."""
    try:
        if not verify_video_file(input_file):
            print(f"Error: {input_file} is not a valid video file.")
            return None
            
        temp_file = os.path.join(temp_dir, get_random_filename())
        command = [
            "ffmpeg", "-i", input_file,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "192k",
            "-y",  # Overwrite output file if it exists
            temp_file
        ]
        
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        if process.returncode != 0:
            print(f"FFmpeg error: {process.stderr}")
            return None
            
        return temp_file
    except Exception as e:
        print(f"Failed to re-encode {input_file}: {e}")
        return None

def rotate_video(input_file: str, output_file: str, angle: int, timeout: int = 120) -> bool:
    """Rotate the video with improved error handling and progress feedback."""
    success = False
    
    def target(input_file: str, output_file: str, angle: int) -> None:
        nonlocal success
        try:
            print(f"Loading video: {input_file}")
            clip = VideoFileClip(input_file)
            
            # Check if the video is vertical
            is_vertical = clip.size[0] < clip.size[1]
            
            # Adjust rotation angle if video is vertical
            if is_vertical and angle in [90, 270]:
                angle += 180
            
            print(f"Rotating video by {angle} degrees...")
            rotated_clip = rotate(clip, angle)
            
            print("Writing rotated video...")
            rotated_clip.write_videofile(
                output_file,
                codec='libx264',
                bitrate='5000k',
                fps=clip.fps,
                threads=4,  # Utilize multiple CPU cores
                logger=None  # Suppress moviepy's verbose logging
            )
            
            # Clean up resources
            rotated_clip.close()
            clip.close()
            
            success = True
            print(f"Video successfully rotated and saved as: {output_file}")
            
        except Exception as e:
            print(f"Error processing {input_file}: {str(e)}")
        finally:
            try:
                clip.close()
            except:
                pass
    
    thread = threading.Thread(target=target, args=(input_file, output_file, angle))
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        print(f"Processing timeout exceeded ({timeout}s) for {input_file}")
        return False
    
    return success

def get_random_filename(extension: str = ".mp4") -> str:
    """Generate a random filename with the specified extension."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(12)) + extension

def create_rotated_directory(base_dir: str) -> str:
    """Create and return the path to the rotated videos directory."""
    rotated_dir = os.path.join(base_dir, "Rotated")
    os.makedirs(rotated_dir, exist_ok=True)
    return rotated_dir

def is_video_file(filename: str) -> bool:
    """Check if the file has a supported video extension."""
    supported_formats = {'.mp4', '.mov', '.webm', '.avi', '.mkv', '.flv', '.wmv'}
    return Path(filename).suffix.lower() in supported_formats

def process_path(path: str, angle: int) -> None:
    """Process either a single video file or a directory of videos."""
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        print(f"Error: Path does not exist: {path}")
        return
        
    # Create a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        if os.path.isfile(path):
            if not is_video_file(path):
                print(f"Error: {path} is not a supported video file.")
                return
                
            rotated_dir = create_rotated_directory(os.path.dirname(path))
            reencoded_file = reencode_video(path, temp_dir)
            
            if reencoded_file:
                output_file = os.path.join(rotated_dir, f"rotated_{os.path.basename(path)}")
                rotate_video(reencoded_file, output_file, angle)
                
        elif os.path.isdir(path):
            rotated_dir = create_rotated_directory(path)
            video_files = [f for f in os.listdir(path) if is_video_file(f)]
            
            if not video_files:
                print(f"No supported video files found in {path}")
                return
                
            print(f"Found {len(video_files)} video files to process...")
            
            for filename in video_files:
                input_file = os.path.join(path, filename)
                reencoded_file = reencode_video(input_file, temp_dir)
                
                if reencoded_file:
                    output_file = os.path.join(rotated_dir, f"rotated_{filename}")
                    rotate_video(reencoded_file, output_file, angle)

def main():
    """Main function with improved user interface."""
    
    # Get input path
    while True:
        input_path = input("\nEnter the path of the video file or directory to rotate: ").strip()
        
        # Handle relative paths
        input_path = os.path.expanduser(input_path)  # Expand ~ to home directory
        input_path = os.path.abspath(input_path)     # Convert to absolute path
        
        if os.path.exists(input_path):
            break
        print("Error: Path not found. Please enter a valid path.")
    
    # Display rotation choices
    print("\nRotation Options:")
    for choice, degrees in rotation_choices.items():
        print(f"{choice}: Rotate {degrees}° clockwise")
    
    # Get rotation choice
    while True:
        user_choice = input("\nEnter your choice (1, 2, 3): ").strip()
        if user_choice in rotation_choices:
            break
        print("Error: Invalid choice. Please choose 1, 2, or 3.")
    
    angle = rotation_choices[user_choice]
    
    print("\nProcessing...")
    process_path(input_path, angle)
    print("\nOperation completed!")

if __name__ == "__main__":
    main()
