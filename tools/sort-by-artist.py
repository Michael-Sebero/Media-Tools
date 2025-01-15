import os
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.mp3 import MP3

def get_artist_and_album(file_path):
    if file_path.lower().endswith('.mp3'):
        audiofile = MP3(file_path, ID3=EasyID3)
    elif file_path.lower().endswith('.flac'):
        audiofile = FLAC(file_path)
    else:
        return None, None

    artist = audiofile.get('artist', [None])[0]
    album = audiofile.get('album', [None])[0]

    return artist, album

def organize_music(directory, recursive=False):
    def process_directory(dir_path):
        for entry in os.scandir(dir_path):
            if entry.is_file() and entry.name.lower().endswith(('.mp3', '.flac', '.opus', '.m4a', '.ogg')):
                artist, album = get_artist_and_album(entry.path)

                if not artist or not album:
                    print(f"Skipped {entry.name} as it has no artist or album information.")
                    continue

                artist_folder = os.path.join(directory, artist)
                if not os.path.exists(artist_folder):
                    os.makedirs(artist_folder)

                album_folder = os.path.join(artist_folder, album)
                if not os.path.exists(album_folder):
                    os.makedirs(album_folder)

                new_file_path = os.path.join(album_folder, entry.name)
                os.rename(entry.path, new_file_path)
                print(f"Moved {entry.name} to {album_folder}")
            elif entry.is_dir() and recursive:
                process_directory(entry.path)

    process_directory(directory)

if __name__ == "__main__":
    user_directory = input("Directory path: ")
    recursive = input("Apply recursively? (y/n): ").lower() == 'y'

    if os.path.isdir(user_directory):
        organize_music(user_directory, recursive)
        print("Music files organized successfully!")
    else:
        print("Invalid directory. Please provide a valid directory.")
