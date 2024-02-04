import os
import shutil
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
import mutagen

def extract_cd_info(file_path):
    """Extract CD information from FLAC or MP3 files."""
    try:
        if file_path.lower().endswith('.flac'):
            audio = FLAC(file_path)
        elif file_path.lower().endswith('.mp3'):
            audio = MP3(file_path)
        else:
            return None

        # Check for disc number metadata (sometimes stored under different tags)
        if 'discnumber' in audio.tags:
            return audio['discnumber'][0]
        elif 'DISKNUMBER' in audio.tags:
            return audio['DISKNUMBER'][0]
        elif 'TXXX:DiscNumber' in audio.tags:
            return audio['TXXX:DiscNumber'][0]
        else:
            return None

    except mutagen.MutagenError:
        return None

def process_directory(directory):
    """Process each file in the directory to determine which CD it belongs to and sort it into folders."""
    cd_sections = {}

    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(('.flac', '.mp3')):
                file_path = os.path.join(root, file)
                cd_info = extract_cd_info(file_path)
                if cd_info:
                    cd_section = f"CD{cd_info}"
                else:
                    cd_section = "Unknown CD"
                
                # Add file to the corresponding CD section
                if cd_section not in cd_sections:
                    cd_sections[cd_section] = []
                cd_sections[cd_section].append(file_path)

    return cd_sections

def create_folders_and_move_files(cd_sections, base_directory):
    """Create folders for each CD section and move the files into them."""
    for cd_section, files in cd_sections.items():
        # Create a folder for the CD section if it doesn't exist
        folder_path = os.path.join(base_directory, cd_section)
        os.makedirs(folder_path, exist_ok=True)
        
        # Move each file to the corresponding folder
        for file_path in files:
            try:
                shutil.move(file_path, folder_path)
                print(f"Moved: {file_path} -> {folder_path}")
            except Exception as e:
                print(f"Error moving {file_path}: {e}")

def main():
    directory = input("Enter the directory containing the music files: ")
    if not os.path.isdir(directory):
        print("Invalid directory!")
        return
    
    # Process directory to group files by CD section
    cd_sections = process_directory(directory)
    
    # Create folders and move files to appropriate CD folders
    create_folders_and_move_files(cd_sections, directory)

if __name__ == "__main__":
    main()
