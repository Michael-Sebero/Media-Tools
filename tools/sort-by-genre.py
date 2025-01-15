import os
from mutagen.easyid3 import EasyID3
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggopus import OggOpus

def get_artist_album_genre(file_path):
    if file_path.lower().endswith('.mp3'):
        audiofile = EasyID3(file_path)
    elif file_path.lower().endswith('.m4a'):
        audiofile = MP4(file_path)
    elif file_path.lower().endswith('.flac'):
        audiofile = FLAC(file_path)
    elif file_path.lower().endswith('.opus'):
        audiofile = OggOpus(file_path)
    elif file_path.lower().endswith('.wav'):
        # WAV files typically do not contain standard metadata
        # You can add additional handling for WAV files if needed
        return None, None, None
    else:
        return None, None, None

    artist = audiofile.get('artist', [None])[0]
    album = audiofile.get('album', [None])[0]
    genre = audiofile.get('genre', ['No Genre'])[0]  # Assign 'No Genre' as default

    return artist, album, genre

def organize_music(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.mp3', '.m4a', '.flac', '.opus', '.wav')):
            file_path = os.path.join(directory, filename)
            artist, album, genre = get_artist_album_genre(file_path)

            print(f"Processing {filename} - Artist: {artist}, Album: {album}, Genre: {genre}")

            # Check if both artist and album are present
            if not artist or not album:
                print(f"Moved {filename} to No Genre folder.")
                no_genre_folder = os.path.join(directory, 'No Genre')
                if not os.path.exists(no_genre_folder):
                    os.makedirs(no_genre_folder)

                new_file_path = os.path.join(no_genre_folder, filename)
                os.rename(file_path, new_file_path)
                continue

            genre_folder = os.path.join(directory, genre)
            if not os.path.exists(genre_folder):
                os.makedirs(genre_folder)

            artist_folder = os.path.join(genre_folder, artist)
            if not os.path.exists(artist_folder):
                os.makedirs(artist_folder)

            album_folder = os.path.join(artist_folder, album)
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
