import os
import shutil
import subprocess
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json

# Adjust this to control grouping granularity
RESOLUTION_BUCKET_SIZE = 200  # e.g. 1920x1080 → 2000x1200
MAX_WORKERS = os.cpu_count() * 2  # Aggressive parallelization
UNIQUE_THRESHOLD = 3  # Resolutions with <= this many files go to "Unique" folder

def get_resolution(file_path):
    """Get resolution with caching and fast path detection"""
    if is_image(file_path):
        return get_resolution_image(file_path)
    elif is_video(file_path):
        return get_resolution_video(file_path)
    return None

def is_image(filename):
    if isinstance(filename, Path):
        ext = filename.suffix.lower()
    else:
        ext = Path(filename).suffix.lower()
    return ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}

def is_video(filename):
    if isinstance(filename, Path):
        ext = filename.suffix.lower()
    else:
        ext = Path(filename).suffix.lower()
    return ext in {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}

def get_resolution_image(filename):
    """Fast image resolution reading - only reads header, not full image"""
    try:
        # Convert Path to string for PIL
        with Image.open(str(filename)) as img:
            return (img.width, img.height)
    except Exception as e:
        print(f"Failed to get image resolution for {filename}: {e}")
        return None

def get_resolution_video(filename):
    """Optimized video resolution detection with hardware decode preference"""
    try:
        # Use the original CSV format that works reliably
        result = subprocess.run([
            "ffprobe", 
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            str(filename)  # Convert Path to string
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        
        output = result.stdout.strip()
        if "x" in output:
            width, height = map(int, output.split("x"))
            return (width, height)
        return None
    except subprocess.TimeoutExpired:
        print(f"Timeout reading {filename}")
        return None
    except Exception as e:
        print(f"Failed to get video resolution for {filename}: {e}")
        return None

def bucket_resolution(width, height, bucket_size):
    """Fast resolution bucketing"""
    bucketed_width = ((width + bucket_size - 1) // bucket_size) * bucket_size
    bucketed_height = ((height + bucket_size - 1) // bucket_size) * bucket_size
    return f"{bucketed_width}x{bucketed_height}"

def process_file(file_path, bucket_size):
    """Process a single file - designed for parallel execution"""
    try:
        res = get_resolution(file_path)
        if res:
            width, height = res
            rounded_res = bucket_resolution(width, height, bucket_size)
            print(f" {file_path.name} -> {width}x{height} -> {rounded_res}")
            return (file_path, rounded_res, True)
        else:
            print(f" Could not get resolution for {file_path.name}")
        return (file_path, None, False)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return (file_path, None, False)

def organize_files(directory):
    """Parallel file processing and batch moving"""
    directory = Path(directory)
    
    # Gather all files first (fast directory scan)
    print("Scanning directory...")
    all_items = os.listdir(directory)
    files = []
    for f in all_items:
        full_path = directory / f
        if full_path.is_file() and (is_image(full_path) or is_video(full_path)):
            files.append(full_path)
    
    if not files:
        print("No image or video files found.")
        return
    
    print(f"Found {len(files)} files. Analyzing resolutions...")
    
    # Process files in parallel
    resolution_map = {}
    processed = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(process_file, f, RESOLUTION_BUCKET_SIZE): f 
            for f in files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            try:
                file_path, rounded_res, success = future.result()
                processed += 1
                
                if success and rounded_res:
                    if rounded_res not in resolution_map:
                        resolution_map[rounded_res] = []
                    resolution_map[rounded_res].append(file_path)
                    print(f" {file_path.name} -> {rounded_res}")
                
                # Progress indicator
                if processed % 100 == 0:
                    print(f"Processed {processed}/{len(files)} files...")
            except Exception as e:
                print(f"ERROR collecting result: {e}")
                processed += 1
    
    print(f"\nAnalysis complete. Found {len(resolution_map)} resolution groups.")
    
    # Separate unique resolutions from common ones
    unique_files = []
    common_resolutions = {}
    
    for rounded_res, file_list in resolution_map.items():
        if len(file_list) <= UNIQUE_THRESHOLD:
            unique_files.extend(file_list)
        else:
            common_resolutions[rounded_res] = file_list
    
    # Create folders and move files (batch operations)
    print("Organizing files...")
    total_moved = 0
    
    # Handle unique files first
    if unique_files:
        unique_folder = directory / "Unique"
        unique_folder.mkdir(exist_ok=True)
        
        for file_path in unique_files:
            try:
                dest_path = unique_folder / file_path.name
                shutil.move(str(file_path), str(dest_path))
                total_moved += 1
            except Exception as e:
                print(f"Failed to move {file_path.name}: {e}")
        
        print(f"  Unique: {len(unique_files)} files (resolutions with 1-{UNIQUE_THRESHOLD} files)")
    
    # Handle common resolutions
    for rounded_res, file_list in common_resolutions.items():
        folder_path = directory / rounded_res
        folder_path.mkdir(exist_ok=True)
        
        # Batch move files
        for file_path in file_list:
            try:
                dest_path = folder_path / file_path.name
                shutil.move(str(file_path), str(dest_path))
                total_moved += 1
            except Exception as e:
                print(f"Failed to move {file_path.name}: {e}")
        
        print(f"  {rounded_res}: {len(file_list)} files")
    
    print(f"\nSuccessfully organized {total_moved} files!")

if __name__ == "__main__":
    input_directory = input("Enter the directory: ").strip()
    if os.path.exists(input_directory) and os.path.isdir(input_directory):
        import time
        start = time.time()
        organize_files(input_directory)
        elapsed = time.time() - start
        print(f"\nCompleted in {elapsed:.2f} seconds.")
    else:
        print("Directory not found or invalid.")
