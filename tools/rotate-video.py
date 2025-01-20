import os
import subprocess
from pathlib import Path

# Dictionary mapping rotation choices to ffmpeg transpose values
rotation_choices = {
    "1": "1",     # 90 degrees clockwise
    "2": "2,2",   # 180 degrees (apply transpose 2 twice)
    "3": "2"      # 90 degrees counterclockwise (270 clockwise)
}

def is_video_file(filename: str) -> bool:
    """Check if the file has a supported video extension."""
    supported_formats = {'.mp4', '.mov', '.webm', '.avi', '.mkv', '.flv', '.wmv'}
    return Path(filename).suffix.lower() in supported_formats

def create_rotated_directory(base_dir: str) -> str:
    """Create and return the path to the rotated videos directory."""
    rotated_dir = os.path.join(base_dir, "Rotated")
    os.makedirs(rotated_dir, exist_ok=True)
    return rotated_dir

def rotate_video(input_file: str, output_file: str, transpose_value: str) -> bool:
    """Rotate video using ffmpeg transpose filter."""
    try:
        if "," in transpose_value:  # Special case for 180 degrees
            filter_command = f"transpose=2,transpose=2"
        else:
            filter_command = f"transpose={transpose_value}"
            
        command = [
            'ffmpeg',
            '-i', input_file,
            '-vf', filter_command,
            '-c:a', 'copy',        # Copy audio without changes
            '-y',                  # Overwrite output if exists
            output_file
        ]
        
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        return process.returncode == 0
    except Exception as e:
        print(f"Error rotating video: {str(e)}")
        return False

def process_path(path: str, transpose_value: str) -> None:
    """Process either a single video file or a directory of videos."""
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        print(f"Error: Path does not exist: {path}")
        return
        
    if os.path.isfile(path):
        if not is_video_file(path):
            print(f"Error: {path} is not a supported video file.")
            return
            
        rotated_dir = create_rotated_directory(os.path.dirname(path))
        output_file = os.path.join(rotated_dir, f"rotated_{os.path.basename(path)}")
        
        if rotate_video(path, output_file, transpose_value):
            print(f"Successfully rotated: {path}")
        else:
            print(f"Failed to rotate: {path}")
            
    elif os.path.isdir(path):
        rotated_dir = create_rotated_directory(path)
        video_files = [f for f in os.listdir(path) if is_video_file(f)]
        
        if not video_files:
            print(f"No supported video files found in {path}")
            return
            
        print(f"Found {len(video_files)} video files to process...")
        
        for filename in video_files:
            input_file = os.path.join(path, filename)
            output_file = os.path.join(rotated_dir, f"rotated_{filename}")
            
            if rotate_video(input_file, output_file, transpose_value):
                print(f"Successfully rotated: {filename}")
            else:
                print(f"Failed to rotate: {filename}")

def main():
    # Get input path
    while True:
        input_path = input("\nEnter the path of the video file or directory to rotate: ").strip()
        
        # Remove any surrounding quotes
        input_path = input_path.strip("'\"")
        
        # Handle relative paths
        input_path = os.path.expanduser(input_path)  # Expand ~ to home directory
        input_path = os.path.abspath(input_path)     # Convert to absolute path
        
        if os.path.exists(input_path):
            break
        print("Error: Path not found. Please enter a valid path.")
    
    # Display rotation choices
    print("\nRotation Options:")
    for choice, degrees in {
        "1": "90",
        "2": "180",
        "3": "270"
    }.items():
        print(f"{choice}: Rotate {degrees}° clockwise")
    
    # Get rotation choice
    while True:
        user_choice = input("\nEnter your choice (1, 2, 3): ").strip()
        if user_choice in rotation_choices:
            break
        print("Error: Invalid choice. Please choose 1, 2, or 3.")
    
    transpose_value = rotation_choices[user_choice]
    
    print("\nProcessing...")
    process_path(input_path, transpose_value)
    print("\nOperation completed!")

if __name__ == "__main__":
    main()
