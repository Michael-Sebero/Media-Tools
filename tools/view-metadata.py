import os
import subprocess
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.easymp4 import EasyMP4
from mutagen.oggvorbis import OggVorbis
from mutagen.oggopus import OggOpus
from mutagen.wavpack import WavPack
from pydub.utils import mediainfo
from moviepy.editor import VideoFileClip

# ANSI escape codes for bold and reset
BOLD = '\033[1m'
RESET = '\033[0m'

def format_duration(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def get_audio_metadata(file_path):
    audio_info = mediainfo(file_path)
    audio = None

    if file_path.lower().endswith('.flac'):
        audio = FLAC(file_path)
    elif file_path.lower().endswith('.mp3'):
        audio = MP3(file_path)
    elif file_path.lower().endswith(('.m4a', '.mp4', '.m4b', '.m4r')):
        audio = EasyMP4(file_path)
    elif file_path.lower().endswith(('.ogg', '.oga')):
        audio = OggVorbis(file_path)
    elif file_path.lower().endswith('.opus'):
        audio = OggOpus(file_path)
    elif file_path.lower().endswith('.wv'):
        audio = WavPack(file_path)
    elif file_path.lower().endswith('.wav'):
        return sorted([
            ("Format", audio_info.get('format_name', None)),
            ("Bitrate", audio_info.get('bit_rate', None)),
            ("Duration", format_duration(float(audio_info.get('duration', 0)))),
            ("Sample Rate", audio_info.get('sample_rate', None)),
        ])

    if audio_info:
        bitrate = audio_info.get('bit_rate', None)
        duration = audio_info.get('duration', None)
        sample_rate = audio_info.get('sample_rate', None)
    else:
        bitrate = getattr(audio.info, 'bitrate', None) if hasattr(audio, 'info') else None
        duration = getattr(audio.info, 'length', None) if hasattr(audio, 'info') else None
        sample_rate = getattr(audio.info, 'sample_rate', None) if hasattr(audio, 'info') else None

    return sorted([
        ("Artist", audio.get("artist", [""])[0] if audio else None),
        ("Album", audio.get("album", [""])[0] if audio else None),
        ("Bitrate", str(bitrate) if bitrate else None),
        ("Duration", format_duration(float(duration)) if duration else None),
        ("Sample Rate", str(sample_rate) if sample_rate else None),
    ])

def get_video_metadata(file_path):
    video = VideoFileClip(file_path)
    ffprobe_cmd = ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    audio_codec = subprocess.check_output(ffprobe_cmd, universal_newlines=True).strip()

    return sorted([
        ("Duration", format_duration(video.duration)),
        ("Resolution", f"{video.size[0]}x{video.size[1]}"),
        ("FPS", str(video.fps)),
        ("Audio Codec", audio_codec if audio_codec else None),
        ("Sample Rate", str(video.audio.fps) if video.audio else None),
    ])

def process_file(file_path):
    if file_path.lower().endswith(('.mp3', '.flac', '.wav', '.aac', '.m4a', '.ogg', '.oga', '.opus', '.wv')):
        print(f"\n{BOLD}File:{RESET} {os.path.basename(file_path)}")
        metadata = get_audio_metadata(file_path)
        for key, value in metadata:
            print(f"{BOLD}{key}{RESET}: {value}")
    elif file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
        print(f"\n{BOLD}File:{RESET} {os.path.basename(file_path)}")
        metadata = get_video_metadata(file_path)
        for key, value in metadata:
            print(f"{BOLD}{key}{RESET}: {value}")

def main():
    path = input("Enter the path to a file or directory: ")

    if not os.path.exists(path):
        print("Path not found. Please provide a valid path.")
        return

    if os.path.isfile(path):
        process_file(path)
    elif os.path.isdir(path):
        filenames = sorted(os.listdir(path))
        for filename in filenames:
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                process_file(file_path)

    print("\nMetadata extraction complete.")

if __name__ == "__main__":
    main()
