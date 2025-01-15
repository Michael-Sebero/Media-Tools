import os
from PIL import Image
from pathlib import Path
import mutagen
from concurrent.futures import ThreadPoolExecutor
import piexif
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.wave import WAVE

def get_image_metadata(file_path):
    """
    Extract metadata from image before removing it
    """
    try:
        with Image.open(file_path) as img:
            metadata = {}
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                if exif:
                    for tag_id in exif:
                        tag = piexif.TAGS.get(tag_id, {})
                        metadata[tag.get('name', tag_id)] = str(exif[tag_id])
            return metadata
    except:
        return {}

def get_video_metadata(file_path):
    """
    Extract metadata from video before removing it
    """
    try:
        media_file = mutagen.File(file_path)
        if media_file is not None:
            return dict(media_file.tags if hasattr(media_file, 'tags') and media_file.tags else {})
        return {}
    except:
        return {}

def remove_image_metadata(file_path):
    """
    Remove metadata from an image file and report what was removed
    """
    try:
        # Get metadata before removal
        metadata = get_image_metadata(file_path)
        
        # Remove metadata
        with Image.open(file_path) as img:
            data = list(img.getdata())
            image_without_exif = Image.new(img.mode, img.size)
            image_without_exif.putdata(data)
            image_without_exif.save(file_path, format=img.format)
        
        # Report removed metadata
        if metadata:
            print(f"\n{file_path}:")
            for key, value in metadata.items():
                print(f"  Removed: {key}: {value}")
        else:
            print(f"\n{file_path}: No metadata found")
            
    except Exception as e:
        print(f"\nError processing {file_path}: {str(e)}")

def remove_video_metadata(file_path):
    """
    Remove metadata from video file and report what was removed
    """
    try:
        # Get metadata before removal
        metadata = get_video_metadata(file_path)
        
        # Remove metadata
        media_file = mutagen.File(file_path)
        if media_file is not None:
            media_file.delete()
            media_file.save()
        
        # Report removed metadata
        if metadata:
            print(f"\n{file_path}:")
            for key, value in metadata.items():
                print(f"  Removed: {key}: {value}")
        else:
            print(f"\n{file_path}: No metadata found")
            
    except Exception as e:
        print(f"\nError processing {file_path}: {str(e)}")

def process_file(file_path):
    """
    Process a single file based on its type
    """
    image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.webp', '.gif', '.bmp'}
    video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm'}
    
    ext = file_path.suffix.lower()
    
    if ext in image_extensions:
        remove_image_metadata(file_path)
    elif ext in video_extensions:
        remove_video_metadata(file_path)

def process_directory(directory_path, recursive=False):
    """
    Process all media files in the directory using multiple threads
    """
    dir_path = Path(directory_path)
    if not dir_path.exists():
        print(f"Directory not found: {directory_path}")
        return
    
    pattern = "**/*" if recursive else "*"
    supported_extensions = {
        '.jpg', '.jpeg', '.png', '.tiff', '.webp', '.gif', '.bmp',
        '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v', '.webm'
    }
    
    # Gather all files first
    files_to_process = [
        f for f in dir_path.glob(pattern)
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]
    
    if not files_to_process:
        print("No supported media files found.")
        return
    
    print(f"\nProcessing {len(files_to_process)} files...")
    
    # Process files in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        executor.map(process_file, files_to_process)

def main():
    directory = input("Directory path: ").strip()
    recursive = input("Apply recursively? (y/n): ").strip().lower() == 'y'
    
    process_directory(directory, recursive)
    print("\nDone!")

if __name__ == "__main__":
    main()
