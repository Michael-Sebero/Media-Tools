from pydub import AudioSegment
from mutagen import File
import os
import shutil

def convert_to_opus(input_folder, output_folder):
    # Create output folder if it doesn't exist
    converted_folder = os.path.join(output_folder, "Converted")
    if not os.path.exists(converted_folder):
        os.makedirs(converted_folder)

    # List to store the paths of the converted files
    converted_files = []

    # Iterate through each file in the input folder
    for filename in os.listdir(input_folder):
        if filename.endswith((".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma")) and not filename.endswith(".opus"):
            input_path = os.path.join(input_folder, filename)

            # Load the audio file
            audio = AudioSegment.from_file(input_path)

            # Retrieve original metadata
            original_file = File(input_path)
            original_metadata = {
                "title": original_file.get("title", ""),
                "artist": original_file.get("artist", ""),
                "album": original_file.get("album", ""),
                "year": original_file.get("date", "")[:4],
                "genre": original_file.get("genre", ""),
                "composer": original_file.get("composer", ""),
                "tracknumber": original_file.get("tracknumber", ""),
            }

            # Extract album art
            if 'covr' in original_file:
                original_metadata['cover'] = original_file['covr'][0]

            # Set output file format to OPUS with libopus codec
            output_format = "opus"
            output_filename = os.path.splitext(filename)[0] + f".{output_format}"
            output_path = os.path.join(converted_folder, output_filename)

            # Set a reasonable bitrate for libopus (e.g., 128 kbps)
            opus_bitrate = 128  # Adjust as needed

            # Export the audio file with libopus codec and specified bitrate
            audio.export(output_path, format=output_format, codec="libopus", bitrate=f"{opus_bitrate}k", tags=original_metadata)

            print(f"Converted: {filename} -> {output_filename}")

            # Add the converted file path to the list
            converted_files.append(output_path)

    return converted_files

if __name__ == "__main__":
    # Get input directory from the user
    input_directory = input("Enter the directory: ")

    # Use the same directory for output
    output_directory = input_directory

    # Convert to OPUS with original metadata and album art, get a list of converted files
    converted_files = convert_to_opus(input_directory, output_directory)

    print("Conversion completed.")
