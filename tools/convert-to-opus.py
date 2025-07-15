from pydub import AudioSegment
from mutagen import File
import os
import shutil

def convert_to_opus(input_folder, output_folder):
    converted_folder = os.path.join(output_folder, "Converted")
    if not os.path.exists(converted_folder):
        os.makedirs(converted_folder)

    converted_files = []
    for filename in os.listdir(input_folder):
        if filename.endswith((".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma")) and not filename.endswith(".opus"):
            input_path = os.path.join(input_folder, filename)

            audio = AudioSegment.from_file(input_path)

            original_file = File(input_path)
            original_metadata = {}
            
            if original_file:
                original_metadata = {
                    "title": str(original_file.get("TIT2", original_file.get("title", [""]))[0]) if original_file.get("TIT2") or original_file.get("title") else "",
                    "artist": str(original_file.get("TPE1", original_file.get("artist", [""]))[0]) if original_file.get("TPE1") or original_file.get("artist") else "",
                    "album": str(original_file.get("TALB", original_file.get("album", [""]))[0]) if original_file.get("TALB") or original_file.get("album") else "",
                    "date": str(original_file.get("TDRC", original_file.get("date", [""]))[0])[:4] if original_file.get("TDRC") or original_file.get("date") else "",
                    "genre": str(original_file.get("TCON", original_file.get("genre", [""]))[0]) if original_file.get("TCON") or original_file.get("genre") else "",
                    "composer": str(original_file.get("TCOM", original_file.get("composer", [""]))[0]) if original_file.get("TCOM") or original_file.get("composer") else "",
                    "tracknumber": str(original_file.get("TRCK", original_file.get("tracknumber", [""]))[0]) if original_file.get("TRCK") or original_file.get("tracknumber") else "",
                }

            output_format = "opus"
            output_filename = os.path.splitext(filename)[0] + f".{output_format}"
            output_path = os.path.join(converted_folder, output_filename)

            opus_bitrate = 320
            
            opus_params = [
                "-c:a", "libopus",
                "-b:a", f"{opus_bitrate}k",
                "-vbr", "on",
                "-compression_level", "10",
                "-frame_duration", "20",
                "-application", "audio",
                "-cutoff", "20000",
                "-mapping_family", "0"
            ]

            audio.export(
                output_path, 
                format=output_format, 
                codec="libopus",
                bitrate=f"{opus_bitrate}k",
                parameters=opus_params,
                tags=original_metadata
            )

            print(f"Converted: {filename} -> {output_filename} (320 kbps VBR)")

            converted_files.append(output_path)

    return converted_files

def convert_to_opus_lossless_source(input_folder, output_folder):
    converted_folder = os.path.join(output_folder, "Converted")
    if not os.path.exists(converted_folder):
        os.makedirs(converted_folder)

    converted_files = []

    for filename in os.listdir(input_folder):
        if filename.endswith((".wav", ".flac")) and not filename.endswith(".opus"):
            input_path = os.path.join(input_folder, filename)

            audio = AudioSegment.from_file(input_path)

            original_file = File(input_path)
            original_metadata = {}
            
            if original_file:
                original_metadata = {
                    "title": str(original_file.get("TIT2", original_file.get("title", [""]))[0]) if original_file.get("TIT2") or original_file.get("title") else "",
                    "artist": str(original_file.get("TPE1", original_file.get("artist", [""]))[0]) if original_file.get("TPE1") or original_file.get("artist") else "",
                    "album": str(original_file.get("TALB", original_file.get("album", [""]))[0]) if original_file.get("TALB") or original_file.get("album") else "",
                    "date": str(original_file.get("TDRC", original_file.get("date", [""]))[0])[:4] if original_file.get("TDRC") or original_file.get("date") else "",
                    "genre": str(original_file.get("TCON", original_file.get("genre", [""]))[0]) if original_file.get("TCON") or original_file.get("genre") else "",
                    "composer": str(original_file.get("TCOM", original_file.get("composer", [""]))[0]) if original_file.get("TCOM") or original_file.get("composer") else "",
                    "tracknumber": str(original_file.get("TRCK", original_file.get("tracknumber", [""]))[0]) if original_file.get("TRCK") or original_file.get("tracknumber") else "",
                }

            output_format = "opus"
            output_filename = os.path.splitext(filename)[0] + f".{output_format}"
            output_path = os.path.join(converted_folder, output_filename)

            opus_bitrate = 448
            
            opus_params = [
                "-c:a", "libopus",
                "-b:a", f"{opus_bitrate}k",
                "-vbr", "on",
                "-compression_level", "10",
                "-frame_duration", "20",
                "-application", "audio",
                "-cutoff", "20000",
                "-mapping_family", "0"
            ]

            audio.export(
                output_path, 
                format=output_format, 
                codec="libopus",
                bitrate=f"{opus_bitrate}k",
                parameters=opus_params,
                tags=original_metadata
            )

            converted_files.append(output_path)

    return converted_files

if __name__ == "__main__":
    input_directory = input("Enter the directory: ")
    source_quality = input("Are your source files lossless (FLAC/WAV)? (y/n): ").lower().strip()
    output_directory = input_directory

    if source_quality == 'y':
        converted_files = convert_to_opus_lossless_source(input_directory, output_directory)
    else:
        converted_files = convert_to_opus(input_directory, output_directory)

    print(f"Total files converted: {len(converted_files)}")
