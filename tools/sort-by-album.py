import os
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

def get_album_name(file_path):
    if file_path.lower().endswith('.mp3'):
        audiofile = MP3(file_path, ID3=EasyID3)
    elif file_path.lower().endswith('.flac'):
        audiofile = FLAC(file_path)
    else:
        # Add support for other formats if needed
        return "No Album"

    if 'album' in audiofile:
        return audiofile['album'][0]
    else:
        return "No Album"

def organize_music(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.mp3', '.flac', '.opus', '.m4a', '.ogg')):
            file_path = os.path.join(directory, filename)
            album_name = get_album_name(file_path)

            album_folder = os.path.join(directory, album_name)
            if not os.path.exists(album_folder):
                os.makedirs(album_folder)

            new_file_path = os.path.join(album_folder, filename)
            os.rename(file_path, new_file_path)
            print(f"Moved {filename} to {album_folder}")

if __name__ == "__main__":
    user_directory = input("Enter the directory of music files: ")

    if os.path.isdir(user_directory):
        organize_music(user_directory)
        print("Music files organized successfully!")
    else:
        print("Invalid directory. Please provide a valid directory.")
