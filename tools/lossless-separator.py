import os
import subprocess
from pydub import AudioSegment
from mutagen.flac import FLAC
from mutagen.apev2 import APEv2
from mutagen.wave import WAVE
import re

def parse_cue_file(cue_path):
    tracks = []
    current_file = None
    with open(cue_path, 'r', encoding='utf-8', errors='ignore') as cue_file:
        for line in cue_file:
            if line.startswith('FILE'):
                current_file = line.split('"')[1]
            elif line.startswith('  TRACK'):
                track_num = int(line.split()[1])
            elif line.startswith('    TITLE'):
                title = line.split('"')[1]
            elif line.startswith('    INDEX 01'):
                time_parts = line.split()[2].split(':')
                time_ms = (int(time_parts[0]) * 60 + int(time_parts[1])) * 1000 + int(time_parts[2]) * 10
                tracks.append((time_ms, title))
    return tracks, current_file

def get_tracks_from_metadata(audio_file):
    try:
        meta = FLAC(audio_file)
    except:
        try:
            meta = APEv2(audio_file)
        except:
            try:
                meta = WAVE(audio_file)
            except:
                return None

    tracks = []
    for key, value in meta.items():
        if key.upper().startswith('CUESHEET'):
            match = re.search(r'TRACK (\d+).*TITLE "(.*)".*INDEX 01 (\d+):(\d+):(\d+)', value[0], re.DOTALL)
            if match:
                track_num, title, min, sec, frame = match.groups()
                time_ms = (int(min) * 60 + int(sec)) * 1000 + int(frame) * 10
                tracks.append((time_ms, title))
        elif key.upper() == 'TRACKNUMBER':
            track_num = int(value[0])
            title = meta.get(f'TITLE:{track_num}', [f'Track {track_num}'])[0]
            # Assume 4-minute tracks if no precise information
            time_ms = (track_num - 1) * 4 * 60 * 1000
            tracks.append((time_ms, title))

    return sorted(tracks) if tracks else None

def split_album_lossless(input_file, output_dir, tracks):
    """Use ffmpeg for lossless splitting when possible"""
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    album_output_dir = os.path.join(output_dir, base_name)
    os.makedirs(album_output_dir, exist_ok=True)

    # Get audio duration using ffprobe
    try:
        result = subprocess.run(['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
                               '-of', 'default=noprint_wrappers=1:nokey=1', input_file], 
                               capture_output=True, text=True)
        duration_seconds = float(result.stdout.strip())
        duration_ms = int(duration_seconds * 1000)
    except:
        # Fallback to pydub for duration
        audio = AudioSegment.from_file(input_file)
        duration_ms = len(audio)

    tracks.append((duration_ms, "End"))

    for i in range(len(tracks) - 1):
        start_time_ms, title = tracks[i]
        end_time_ms = tracks[i+1][0]

        start_seconds = start_time_ms / 1000
        duration_seconds = (end_time_ms - start_time_ms) / 1000

        safe_title = re.sub(r'[^\w\-_\. ]', '_', title)
        
        # Determine output format based on input
        _, ext = os.path.splitext(input_file)
        ext = ext.lower()
        
        if ext == '.wav':
            output_file = os.path.join(album_output_dir, f"{i+1:02d} - {safe_title}.wav")
            # Use ffmpeg for lossless WAV splitting
            cmd = ['ffmpeg', '-i', input_file, '-ss', str(start_seconds), 
                   '-t', str(duration_seconds), '-c', 'copy', '-avoid_negative_ts', 'make_zero', 
                   output_file, '-y']
        elif ext == '.flac':
            output_file = os.path.join(album_output_dir, f"{i+1:02d} - {safe_title}.flac")
            # Use ffmpeg for lossless FLAC splitting
            cmd = ['ffmpeg', '-i', input_file, '-ss', str(start_seconds), 
                   '-t', str(duration_seconds), '-c', 'copy', '-avoid_negative_ts', 'make_zero',
                   output_file, '-y']
        else:
            # Fallback to pydub for other formats
            output_file = os.path.join(album_output_dir, f"{i+1:02d} - {safe_title}{ext}")
            audio = AudioSegment.from_file(input_file)
            segment = audio[start_time_ms:end_time_ms]
            segment.export(output_file, format=ext[1:])
            print(f"Exported (pydub): {output_file}")
            continue

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Exported (lossless): {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"ffmpeg failed for {title}, falling back to pydub...")
            # Fallback to pydub
            audio = AudioSegment.from_file(input_file)
            segment = audio[start_time_ms:end_time_ms]
            segment.export(output_file, format=ext[1:])
            print(f"Exported (pydub): {output_file}")

def split_album(input_file, output_dir):
    base_name, ext = os.path.splitext(input_file)
    ext = ext.lower()

    if ext == '.ape':
        print(f"Converting {input_file} from APE to FLAC...")
        flac_file = base_name + '.flac'
        subprocess.run(['ffmpeg', '-i', input_file, flac_file])
        input_file = flac_file
        ext = '.flac'

    # Check for corresponding .cue file
    cue_file = base_name + '.cue'
    if os.path.exists(cue_file):
        print(f"Found cue file: {cue_file}")
        tracks, cue_audio_file = parse_cue_file(cue_file)
        if cue_audio_file and os.path.basename(cue_audio_file) != os.path.basename(input_file):
            print(f"Warning: Cue file references a different audio file: {cue_audio_file}")
    else:
        tracks = get_tracks_from_metadata(input_file)

    if not tracks:
        print(f"Could not extract track information from {input_file} or its cue file. Skipping this file.")
        return

    # Use lossless splitting for WAV and FLAC files
    if ext in ['.wav', '.flac']:
        split_album_lossless(input_file, output_dir, tracks)
    else:
        # Fallback to pydub for other formats
        audio = AudioSegment.from_file(input_file, format=ext[1:])
        album_name = os.path.splitext(os.path.basename(input_file))[0]
        album_output_dir = os.path.join(output_dir, album_name)
        os.makedirs(album_output_dir, exist_ok=True)

        tracks.append((len(audio), "End"))

        for i in range(len(tracks) - 1):
            start_time, title = tracks[i]
            end_time = tracks[i+1][0]

            segment = audio[start_time:end_time]

            safe_title = re.sub(r'[^\w\-_\. ]', '_', title)
            output_file = os.path.join(album_output_dir, f"{i+1:02d} - {safe_title}{ext}")

            segment.export(output_file, format=ext[1:])
            print(f"Exported: {output_file}")

    print(f"Album splitting complete for {input_file}!")

def process_directory(directory):
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.flac', '.ape', '.wav')):
            input_file = os.path.join(directory, filename)
            print(f"Processing file: {input_file}")
            try:
                split_album(input_file, directory)
            except Exception as e:
                print(f"Error processing {input_file}: {str(e)}")

# Get input from user
input_dir = input("Enter the directory containing FLAC, APE, or WAV files: ")

# Run the function
process_directory(input_dir)
