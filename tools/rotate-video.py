import os
import struct
import shutil
import sys
import subprocess
from pathlib import Path

class VideoRotator:
    """Base class for video rotators"""
    
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
    
    def rotate(self, degrees):
        """Rotate the video - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement rotate()")


class MP4Rotator(VideoRotator):
    
    # Rotation matrix values for different angles (in 'tkhd' atom)
    # Format: [a, b, c, d] corresponding to the matrix [a b 0; c d 0; 0 0 1]
    ROTATION_MATRICES = {
        "90":  [0, 1, -1, 0],    # 90 degrees clockwise
        "180": [-1, 0, 0, -1],   # 180 degrees
        "270": [0, -1, 1, 0]     # 270 degrees clockwise (90 counterclockwise)
    }
    
    def __init__(self, input_file, output_file):
        self.input_file = input_file
        self.output_file = output_file
        
    def rotate(self, degrees):
        """Rotate the video by modifying the MP4 container metadata."""
        try:
            # First make a copy of the file to work with
            shutil.copy2(self.input_file, self.output_file)
            
            # Open the file in read+write binary mode
            with open(self.output_file, 'r+b') as f:
                self._process_atoms(f, degrees)
                
            print(f"Successfully rotated: {Path(self.input_file).name}")
            return True
        except Exception as e:
            print(f"Error rotating video: {str(e)}")
            # Clean up failed output if it exists
            if os.path.exists(self.output_file):
                os.remove(self.output_file)
            return False
    
    def _process_atoms(self, file_handle, degrees):
        """Process the MP4 atoms to find and modify the track header."""
        # Start from the beginning of the file
        file_handle.seek(0)
        
        # Read file size and file type
        size = self._read_uint32(file_handle)
        file_type = file_handle.read(4)
        
        if file_type != b'ftyp':
            raise ValueError("Not a valid MP4 file (missing 'ftyp' atom)")
        
        # Skip to the end of the ftyp atom
        file_handle.seek(size, os.SEEK_SET)
        
        # Process remaining atoms at the top level
        while True:
            pos = file_handle.tell()
            if pos >= os.path.getsize(self.output_file):
                break
                
            try:
                atom_size = self._read_uint32(file_handle)
                atom_type = file_handle.read(4)
                
                if atom_type == b'moov':
                    # Process the movie atom which contains track information
                    self._process_moov_atom(file_handle, pos + 8, atom_size - 8, degrees)
                
                # Move to the next atom
                file_handle.seek(pos + atom_size)
            except Exception as e:
                print(f"Error processing atom at position {pos}: {str(e)}")
                break
    
    def _process_moov_atom(self, file_handle, start_pos, size, degrees):
        """Process the 'moov' atom to find and process track atoms."""
        end_pos = start_pos + size
        
        # Position at the start of moov content
        file_handle.seek(start_pos)
        
        while file_handle.tell() < end_pos:
            atom_pos = file_handle.tell()
            atom_size = self._read_uint32(file_handle)
            atom_type = file_handle.read(4)
            
            if atom_type == b'trak':
                # Process the track atom which contains track header
                self._process_trak_atom(file_handle, atom_pos + 8, atom_size - 8, degrees)
            
            # Move to the next atom in moov
            next_pos = atom_pos + atom_size
            if next_pos >= end_pos:
                break
            file_handle.seek(next_pos)
    
    def _process_trak_atom(self, file_handle, start_pos, size, degrees):
        """Process the 'trak' atom to find the track header."""
        end_pos = start_pos + size
        
        # Position at the start of trak content
        file_handle.seek(start_pos)
        
        while file_handle.tell() < end_pos:
            atom_pos = file_handle.tell()
            atom_size = self._read_uint32(file_handle)
            atom_type = file_handle.read(4)
            
            if atom_type == b'tkhd':
                # Found the track header, modify it
                self._modify_tkhd_atom(file_handle, atom_pos, atom_size, degrees)
            
            # Move to the next atom in trak
            next_pos = atom_pos + atom_size
            if next_pos >= end_pos:
                break
            file_handle.seek(next_pos)
    
    def _modify_tkhd_atom(self, file_handle, atom_pos, atom_size, degrees):
        """Modify the track header atom to apply rotation."""
        # Read the version/flags (first 4 bytes of the atom content)
        file_handle.seek(atom_pos + 8)
        version_flags = self._read_uint32(file_handle)
        version = (version_flags >> 24) & 0xFF
        
        # Determine offset to the matrix based on version
        # Version 0: 52 bytes to matrix, Version 1: 60 bytes to matrix
        matrix_offset = 60 if version == 1 else 52
        
        # Position at the matrix data
        matrix_pos = atom_pos + 8 + matrix_offset
        file_handle.seek(matrix_pos)
        
        # Get the rotation matrix values
        rotation_values = self.ROTATION_MATRICES.get(degrees)
        if not rotation_values:
            raise ValueError(f"Unsupported rotation angle: {degrees}")
        
        # Write the new matrix values (a, b, c, d)
        # Each value is stored as a 32-bit fixed-point number (16.16 format)
        for value in rotation_values:
            # Convert to fixed-point 16.16 format
            fixed_point = int(value * 65536)
            file_handle.write(struct.pack('>i', fixed_point))
            
        # Skip u (value after d in the matrix)
        file_handle.seek(4, os.SEEK_CUR)
        
        # Write the unchanged identity values for the rest of the matrix
        # Values for [0 0 1] part are typically [0, 0, 1<<16]
        file_handle.write(struct.pack('>i', 0))  # x
        file_handle.write(struct.pack('>i', 0))  # y
        file_handle.write(struct.pack('>i', 65536))  # z (1.0 in fixed point)
    
    def _read_uint32(self, file_handle):
        """Read a 32-bit unsigned integer (big-endian) from the file."""
        data = file_handle.read(4)
        if len(data) < 4:
            raise EOFError("Unexpected end of file")
        return struct.unpack('>I', data)[0]


def is_video_file(filename: str) -> bool:
    """Check if the file has a supported video extension."""
    # Support common video formats
    supported_formats = {
        '.mp4', '.mov', '.m4v',   # QuickTime/MPEG-4 container formats
        '.avi', '.divx',          # AVI container formats
        '.wmv',                   # Windows Media formats
        '.mkv', '.webm',          # Matroska container formats
        '.flv', '.f4v',           # Flash video formats
        '.3gp', '.3g2',           # Mobile video formats
        '.ts', '.mts', '.m2ts'    # Transport stream formats
    }
    return Path(filename).suffix.lower() in supported_formats


def get_video_dimensions(video_path):
    """Get video dimensions using FFmpeg"""
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        dimensions = result.stdout.strip().split(',')
        if len(dimensions) == 2:
            return int(dimensions[0]), int(dimensions[1])
    except Exception as e:
        print(f"Warning: Could not get video dimensions: {e}")
    
    # Return None if we couldn't get dimensions
    return None, None


def get_rotator_for_file(input_file: str, output_file: str):
    """Factory function to get appropriate rotator based on file extension and available tools."""
    # For all formats, prefer FFmpeg if available
    if check_for_ffmpeg():
        return FFMpegRotator(input_file, output_file)
    
    # If no FFmpeg is available, try metadata rotation for MP4/MOV
    ext = Path(input_file).suffix.lower()
    if ext in {'.mp4', '.mov', '.m4v'}:
        print("Note: Using metadata rotation. Some players may not respect this.")
        print("      For best results, install FFmpeg.")
        return MP4Rotator(input_file, output_file)
    
    # Fallback to copy
    print(f"Warning: Cannot rotate {Path(input_file).name} without FFmpeg.")
    print("         File will be copied without rotation.")
    print("         To enable rotation, install FFmpeg.")
    return CopyRotator(input_file, output_file)


def check_for_ffmpeg():
    """Check if ffmpeg is available on the system."""
    try:
        # Try to run ffmpeg -version
        subprocess.run(
            ['ffmpeg', '-version'], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=False
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


class FFMpegRotator(VideoRotator):
    """Rotator that uses FFmpeg for formats where metadata rotation doesn't work."""
    
    # Map rotation degrees to FFmpeg transpose values
    TRANSPOSE_VALUES = {
        "90": "1",     # 90 degrees clockwise
        "270": "2"     # 90 degrees counterclockwise (270 clockwise)
    }
    
    def rotate(self, degrees):
        """Rotate video using FFmpeg with proper dimension handling"""
        try:
            # For 90 and 270 degrees, we need to swap dimensions and use transpose
            # For 180 degrees, we just use the hflip+vflip filters
            
            if degrees == "180":
                # 180 degrees: use horizontal and vertical flip (no dimension change)
                vf_filter = "hflip,vflip"
                swap_dimensions = False
            elif degrees in self.TRANSPOSE_VALUES:
                # 90 or 270 degrees: use transpose (swaps dimensions)
                vf_filter = f"transpose={self.TRANSPOSE_VALUES[degrees]}"
                swap_dimensions = True
            else:
                print(f"Error: Unsupported rotation angle: {degrees}")
                return False
            
            # Build FFmpeg command
            command = [
                'ffmpeg',
                '-i', self.input_file,
                '-c:v', 'libx264',         # Use H.264 codec for video
                '-crf', '18',              # High quality setting (lower is better)
                '-preset', 'medium',       # Balance between speed and compression
                '-c:a', 'copy',            # Copy audio without changes
                '-vf', vf_filter,          # Apply rotation filter
                '-metadata:s:v', 'rotate=0',  # Clear any existing rotation metadata
                '-y',                      # Overwrite output if exists
                self.output_file
            ]
            
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            if process.returncode == 0:
                print(f"Successfully rotated: {Path(self.input_file).name}")
                return True
            else:
                print(f"FFmpeg error: {process.stderr}")
                return False
        except Exception as e:
            print(f"Error rotating video with FFmpeg: {str(e)}")
            if os.path.exists(self.output_file):
                os.remove(self.output_file)
            return False


class CopyRotator(VideoRotator):
    """Fallback rotator for when neither metadata rotation nor FFmpeg is available."""
    
    def rotate(self, degrees):
        """Make a copy of the file and show rotation instructions."""
        try:
            shutil.copy2(self.input_file, self.output_file)
            print(f"Note: {Path(self.input_file).name} copied but not rotated.")
            return True
        except Exception as e:
            print(f"Error copying video: {str(e)}")
            if os.path.exists(self.output_file):
                os.remove(self.output_file)
            return False

def create_rotated_directory(base_dir: str) -> str:
    """Create and return the path to the rotated videos directory."""
    rotated_dir = os.path.join(base_dir, "Rotated")
    os.makedirs(rotated_dir, exist_ok=True)
    return rotated_dir

def rotate_video(input_file: str, output_file: str, degrees: str) -> bool:
    """Rotate video using the appropriate rotator for the file type."""
    rotator = get_rotator_for_file(input_file, output_file)
    return rotator.rotate(degrees)

def process_path(path: str, degrees: str) -> None:
    """Process either a single video file or a directory of videos."""
    path = os.path.abspath(path)
    
    if not os.path.exists(path):
        print(f"Error: Path does not exist: {path}")
        return
        
    if os.path.isfile(path):
        if not is_video_file(path):
            print(f"Error: {path} is not a supported video file.")
            print(f"Supported formats: MP4, MOV, MKV, AVI, WMV, WEBM, FLV, and more.")
            return
            
        rotated_dir = create_rotated_directory(os.path.dirname(path))
        output_file = os.path.join(rotated_dir, f"rotated_{os.path.basename(path)}")
        
        if rotate_video(path, output_file, degrees):
            print(f"Successfully rotated: {path}")
        else:
            print(f"Failed to rotate: {path}")
            
    elif os.path.isdir(path):
        rotated_dir = create_rotated_directory(path)
        video_files = [f for f in os.listdir(path) if is_video_file(os.path.join(path, f))]
        
        if not video_files:
            print(f"No supported video files found in {path}")
            return
            
        print(f"Found {len(video_files)} video files to process...")
        
        for filename in video_files:
            input_file = os.path.join(path, filename)
            output_file = os.path.join(rotated_dir, f"rotated_{filename}")
            
            if rotate_video(input_file, output_file, degrees):
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
    rotation_options = {
        "1": "90",
        "2": "180",
        "3": "270"
    }
    
    for choice, degrees in rotation_options.items():
        print(f"{choice}: Rotate {degrees}° clockwise")
    
    # Get rotation choice
    while True:
        user_choice = input("\nEnter your choice (1, 2, 3): ").strip()
        if user_choice in rotation_options:
            break
        print("Error: Invalid choice. Please choose 1, 2, or 3.")
    
    degrees = rotation_options[user_choice]
    
    print("\nProcessing...")
    process_path(input_path, degrees)
    print("\nOperation completed!")

if __name__ == "__main__":
    main()
