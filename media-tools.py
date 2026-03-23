#!/usr/bin/env python3
import os
import sys
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from enum import Enum

# Third-party imports
try:
    from PIL import Image, ImageChops
    from mutagen import File as MutagenFile
    from mutagen.flac import FLAC, Picture as FlacPicture
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, APIC
    from mutagen.mp4 import MP4
    from mutagen.oggopus import OggOpus
    from mutagen.oggvorbis import OggVorbis
    import eyed3
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("Install: pip install pillow mutagen eyeD3 --break-system-packages")
    sys.exit(1)


class MediaExtensions:
    AUDIO = {'.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.aac', '.ape'}
    VIDEO = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
    IMAGE = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    LOSSLESS_AUDIO = {'.flac', '.wav', '.ape'}
    
    @classmethod
    def is_audio(cls, filepath: Path) -> bool:
        return filepath.suffix.lower() in cls.AUDIO
    
    @classmethod
    def is_video(cls, filepath: Path) -> bool:
        return filepath.suffix.lower() in cls.VIDEO
    
    @classmethod
    def is_image(cls, filepath: Path) -> bool:
        return filepath.suffix.lower() in cls.IMAGE


class PathUtils:
    @staticmethod
    def ensure_output_dir(base_dir: Path, subfolder: str = "Output") -> Path:
        output_dir = base_dir / subfolder
        output_dir.mkdir(exist_ok=True)
        return output_dir
    
    @staticmethod
    def get_valid_path(prompt: str = "Enter path: ") -> Path:
        while True:
            path_str = input(prompt).strip().strip("'\"")
            if not path_str:
                print("Error: Path cannot be empty.")
                continue
            path = Path(os.path.expanduser(path_str)).resolve()
            if path.exists():
                return path
            print("Error: Path not found.")
    
    @staticmethod
    def sanitize_filename(name: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '_', name)


class AudioMetadata:
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.audio = self._load_audio()
    
    def _load_audio(self):
        ext = self.filepath.suffix.lower()
        try:
            if ext == '.mp3':
                return MP3(self.filepath, ID3=EasyID3)
            elif ext == '.flac':
                return FLAC(self.filepath)
            elif ext in {'.m4a', '.mp4'}:
                return MP4(self.filepath)
            elif ext == '.opus':
                return OggOpus(self.filepath)
            elif ext == '.ogg':
                return OggVorbis(self.filepath)
            else:
                return MutagenFile(self.filepath)
        except:
            return None
    
    def get(self, field: str, default: Optional[str] = None) -> Optional[str]:
        if not self.audio:
            return default
        
        if isinstance(self.audio, MP4):
            mp4_map = {
                'artist': '\xa9ART',
                'album': '\xa9alb',
                'title': '\xa9nam',
                'genre': '\xa9gen',
                'date': '\xa9day',
                'discnumber': 'disk',
            }
            key = mp4_map.get(field, field)
            if key in self.audio.tags:
                value = self.audio.tags[key]
                return str(value[0]) if isinstance(value, list) else str(value)
            return default
        
        if field not in self.audio:
            return default
        value = self.audio[field]
        return str(value[0]) if isinstance(value, list) else str(value)


class FileScanner:
    @staticmethod
    def scan(directory: Path, extensions: set, recursive: bool = False) -> List[Path]:
        pattern = "**/*" if recursive else "*"
        return [f for f in directory.glob(pattern) if f.is_file() and f.suffix.lower() in extensions]
    
    @staticmethod
    def scan_audio(directory: Path, recursive: bool = False) -> List[Path]:
        return FileScanner.scan(directory, MediaExtensions.AUDIO, recursive)
    
    @staticmethod
    def scan_video(directory: Path, recursive: bool = False) -> List[Path]:
        return FileScanner.scan(directory, MediaExtensions.VIDEO, recursive)
    
    @staticmethod
    def scan_image(directory: Path, recursive: bool = False) -> List[Path]:
        return FileScanner.scan(directory, MediaExtensions.IMAGE, recursive)


class UserInput:
    @staticmethod
    def yes_no(prompt: str, default: bool = False) -> bool:
        resp = input(f"{prompt} ({'Y/n' if default else 'y/N'}): ").strip().lower()
        return resp in {'y', 'yes'} if resp else default
    
    @staticmethod
    def choice(prompt: str, options: dict) -> str:
        print(prompt)
        for key, desc in options.items():
            print(f"  {key}: {desc}")
        while True:
            c = input("Enter choice: ").strip()
            if c in options:
                return c
            print(f"Invalid. Choose: {', '.join(options.keys())}")
    
    @staticmethod
    def number(prompt: str, min_val: float = None, max_val: float = None) -> float:
        while True:
            try:
                val = float(input(prompt).strip())
                if min_val and val < min_val:
                    print(f"Must be >= {min_val}")
                    continue
                if max_val and val > max_val:
                    print(f"Must be <= {max_val}")
                    continue
                return val
            except ValueError:
                print("Enter a valid number.")


def get_key():
    import termios, tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                if ch3 == 'A': return 'UP'
                elif ch3 == 'B': return 'DOWN'
        elif ch in '\r\n': return 'ENTER'
        elif ch == '\x03': return 'CTRL_C'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def clear():
    os.system('clear')


def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except:
        return False


# ============================================================================
# TOOL 1-3: MUSIC ORGANIZERS
# ============================================================================

class MusicOrganizer:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.stats = {'moved': 0, 'skipped': 0, 'failed': 0}
    
    def by_artist(self, recursive: bool = False):
        files = FileScanner.scan_audio(self.base_dir, recursive)
        if not files:
            print("No audio files found.")
            return
        
        print(f"Organizing {len(files)} files by Artist > Album...")
        for f in files:
            try:
                meta = AudioMetadata(f)
                artist = meta.get('artist')
                album = meta.get('album')
                
                if not artist or not album:
                    print(f"Skip {f.name} - missing metadata")
                    self.stats['skipped'] += 1
                    continue
                
                dest = self.base_dir / PathUtils.sanitize_filename(artist) / PathUtils.sanitize_filename(album)
                dest.mkdir(parents=True, exist_ok=True)
                dest_path = dest / f.name
                
                if dest_path.exists():
                    self.stats['skipped'] += 1
                    continue
                
                f.rename(dest_path)
                print(f"OK {f.name} -> {artist}/{album}/")
                self.stats['moved'] += 1
            except Exception as e:
                print(f"ERR {f.name}: {e}")
                self.stats['failed'] += 1
        
        print(f"\nMoved: {self.stats['moved']} | Skipped: {self.stats['skipped']} | Failed: {self.stats['failed']}")
    
    def by_album(self):
        files = FileScanner.scan_audio(self.base_dir, False)
        if not files:
            print("No audio files found.")
            return
        
        print(f"Organizing {len(files)} files by Album...")
        for f in files:
            try:
                meta = AudioMetadata(f)
                album = meta.get('album', 'No Album')
                dest = self.base_dir / PathUtils.sanitize_filename(album)
                dest.mkdir(exist_ok=True)
                dest_path = dest / f.name
                
                if not dest_path.exists():
                    f.rename(dest_path)
                    print(f"OK {f.name} -> {album}/")
                    self.stats['moved'] += 1
                else:
                    self.stats['skipped'] += 1
            except Exception as e:
                print(f"ERR {f.name}: {e}")
                self.stats['failed'] += 1
        
        print(f"\nMoved: {self.stats['moved']} | Skipped: {self.stats['skipped']}")
    
    def by_genre(self):
        files = FileScanner.scan_audio(self.base_dir, False)
        if not files:
            print("No audio files found.")
            return
        
        print(f"Organizing {len(files)} files by Genre > Artist > Album...")
        for f in files:
            try:
                meta = AudioMetadata(f)
                artist = meta.get('artist')
                album = meta.get('album')
                genre = meta.get('genre', 'No Genre')
                
                if not artist or not album:
                    dest = self.base_dir / 'No Genre'
                else:
                    dest = self.base_dir / PathUtils.sanitize_filename(genre) / PathUtils.sanitize_filename(artist) / PathUtils.sanitize_filename(album)
                
                dest.mkdir(parents=True, exist_ok=True)
                dest_path = dest / f.name
                
                if not dest_path.exists():
                    f.rename(dest_path)
                    print(f"OK {f.name}")
                    self.stats['moved'] += 1
                else:
                    self.stats['skipped'] += 1
            except Exception as e:
                print(f"ERR {f.name}: {e}")
                self.stats['failed'] += 1
        
        print(f"\nMoved: {self.stats['moved']} | Skipped: {self.stats['skipped']}")


# ============================================================================
# TOOL 4: GENERATE ALBUM SECTIONS (BY DISC)
# ============================================================================

def organize_by_disc(directory: Path):
    files = FileScanner.scan_audio(directory, False)
    if not files:
        print("No audio files found.")
        return
    
    print(f"Organizing {len(files)} files by disc number...")
    moved = 0
    for f in files:
        try:
            meta = AudioMetadata(f)
            disc = meta.get('discnumber', 'Unknown CD')
            
            if disc and disc != 'Unknown CD':
                disc_num = disc.split('/')[0] if '/' in disc else disc
                folder_name = f"CD{disc_num}"
            else:
                folder_name = 'Unknown CD'
            
            dest = directory / folder_name
            dest.mkdir(exist_ok=True)
            dest_path = dest / f.name
            
            if not dest_path.exists():
                f.rename(dest_path)
                print(f"OK {f.name} -> {folder_name}/")
                moved += 1
        except Exception as e:
            print(f"ERR {f.name}: {e}")
    
    print(f"\nMoved: {moved} files")


# ============================================================================
# TOOL 5: CHANGE VOLUME
# ============================================================================

def adjust_volume(files: List[Path], db: float, output: Path):
    output.mkdir(exist_ok=True)
    ok, fail = 0, 0
    for f in files:
        try:
            out = output / f.name
            r = subprocess.run(['ffmpeg', '-i', str(f), '-af', f'volume={db}dB', '-y', str(out)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode == 0:
                print(f"OK {f.name} ({db:+.1f} dB)")
                ok += 1
            else:
                print(f"ERR {f.name}")
                fail += 1
        except Exception as e:
            print(f"ERR {f.name}: {e}")
            fail += 1
    print(f"\nProcessed: {ok} | Failed: {fail}")


# ============================================================================
# TOOL 6: COMPARE AUDIO (SPECTROGRAMS)
# ============================================================================

def compare_audio_spectrograms(file1: Path, file2: Path):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        
        # Check if librosa is available
        try:
            import librosa
            import librosa.display
        except ImportError:
            print("Error: librosa not installed.")
            print("Install: pip install librosa --break-system-packages")
            return
        
        print("Generating spectrograms (this may take a moment)...")
        
        fig, axs = plt.subplots(2, 1, figsize=(10, 8))
        
        for i, (filepath, ax) in enumerate(zip([file1, file2], axs)):
            try:
                y, sr = librosa.load(str(filepath), duration=8*60)
                D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)
                img = librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log', ax=ax)
                ax.set_title(filepath.name)
                plt.colorbar(img, ax=ax, format="%+2.0f dB")
            except Exception as e:
                print(f"Error processing {filepath.name}: {e}")
                return
        
        plt.tight_layout()
        
        desktop = Path.home() / "Desktop"
        if not desktop.exists():
            desktop = Path.home()
        
        output = desktop / "comparison.png"
        plt.savefig(output)
        print(f"\nComparison saved to: {output}")
        
    except ImportError as e:
        print(f"Error: Missing library: {e}")
        print("Install: pip install matplotlib librosa --break-system-packages")


# ============================================================================
# TOOL 7: CONVERT TO OPUS
# ============================================================================

def convert_opus(files: List[Path], lossless: bool, output: Path):
    output.mkdir(exist_ok=True)
    bitrate = 448 if lossless else 320
    ok, fail = 0, 0
    for f in files:
        try:
            out = output / f"{f.stem}.opus"
            r = subprocess.run(['ffmpeg', '-i', str(f), '-c:a', 'libopus', '-b:a', f'{bitrate}k',
                              '-vbr', 'on', '-y', str(out)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode == 0:
                print(f"OK {f.name} -> {out.name} ({bitrate}k)")
                ok += 1
            else:
                fail += 1
        except Exception as e:
            print(f"ERR {f.name}: {e}")
            fail += 1
    print(f"\nConverted: {ok} | Failed: {fail}")


# ============================================================================
# TOOL 8: LOSSLESS SEPARATOR (CUE SPLITTER)
# ============================================================================

def split_lossless_album(filepath: Path):
    base_name = filepath.stem
    cue_file = filepath.parent / f"{base_name}.cue"
    
    if not cue_file.exists():
        print(f"No CUE file found: {cue_file.name}")
        return
    
    output_dir = filepath.parent / base_name
    output_dir.mkdir(exist_ok=True)
    
    print(f"Splitting {filepath.name} using {cue_file.name}...")
    
    try:
        # Try using shnsplit
        result = subprocess.run(
            ['shnsplit', '-f', str(cue_file), '-o', 'flac', '-t', '%n - %t',
             '-d', str(output_dir), str(filepath)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if result.returncode == 0:
            print(f"OK Split {filepath.name} successfully")
            print(f"Output: {output_dir}")
        else:
            print(f"ERR Failed to split")
            print("Note: Install shntool and flac packages")
    except FileNotFoundError:
        print("Error: shnsplit not found")
        print("Install: sudo pacman -S shntool flac")
    except Exception as e:
        print(f"ERR {e}")


# ============================================================================
# TOOL 9: MASS THUMBNAIL
# ============================================================================

def add_thumbnails(files: List[Path], thumb: Path):
    with open(thumb, 'rb') as img:
        data = img.read()
    mime = 'image/jpeg' if thumb.suffix.lower() in {'.jpg', '.jpeg'} else 'image/png'
    ok, fail = 0, 0
    
    for f in files:
        try:
            ext = f.suffix.lower()
            if ext == '.mp3':
                audio = eyed3.load(f)
                if not audio.tag:
                    audio.initTag()
                audio.tag.images.set(3, data, mime)
                audio.tag.save()
                print(f"OK {f.name}")
                ok += 1
            elif ext == '.flac':
                audio = FLAC(f)
                pic = FlacPicture()
                pic.type = 3
                pic.mime = mime
                pic.data = data
                audio.add_picture(pic)
                audio.save()
                print(f"OK {f.name}")
                ok += 1
        except Exception as e:
            print(f"ERR {f.name}: {e}")
            fail += 1
    print(f"\nProcessed: {ok} | Failed: {fail}")


# ============================================================================
# TOOL 10: REMOVE AUDIO FROM VIDEO
# ============================================================================

def remove_video_audio(files: List[Path], output: Path):
    output.mkdir(exist_ok=True)
    ok, fail = 0, 0
    for f in files:
        try:
            out = output / f.name
            r = subprocess.run(['ffmpeg', '-i', str(f), '-c', 'copy', '-an', '-y', str(out)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode == 0:
                print(f"OK {f.name}")
                ok += 1
            else:
                fail += 1
        except:
            fail += 1
    print(f"\nProcessed: {ok} | Failed: {fail}")


# ============================================================================
# TOOL 11: REMOVE METADATA
# ============================================================================

def remove_metadata(files: List[Path]):
    ok, fail = 0, 0
    for f in files:
        try:
            if MediaExtensions.is_image(f):
                with Image.open(f) as img:
                    data = list(img.getdata())
                    clean = Image.new(img.mode, img.size)
                    clean.putdata(data)
                    clean.save(f, format=img.format)
                print(f"OK {f.name}")
                ok += 1
            elif MediaExtensions.is_video(f):
                media = MutagenFile(f)
                if media:
                    media.delete()
                    media.save()
                print(f"OK {f.name}")
                ok += 1
        except Exception as e:
            print(f"ERR {f.name}: {e}")
            fail += 1
    print(f"\nProcessed: {ok} | Failed: {fail}")


# ============================================================================
# TOOL 12: ROTATE VIDEO
# ============================================================================

def rotate_videos(files: List[Path], degrees: int, output: Path):
    output.mkdir(exist_ok=True)
    filters = {90: 'transpose=1', 180: 'hflip,vflip', 270: 'transpose=2'}
    if degrees not in filters:
        print("Invalid rotation")
        return
    
    ok, fail = 0, 0
    for f in files:
        try:
            out = output / f"rotated_{f.name}"
            r = subprocess.run(['ffmpeg', '-i', str(f), '-vf', filters[degrees], '-c:a', 'copy', '-y', str(out)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode == 0:
                print(f"OK {f.name} ({degrees} deg)")
                ok += 1
            else:
                fail += 1
        except:
            fail += 1
    print(f"\nProcessed: {ok} | Failed: {fail}")


# ============================================================================
# TOOL 13: SAMPLE RATE DETECTOR
# ============================================================================

def monitor_sample_rate():
    print("Monitoring audio sample rate (Ctrl+C to stop)...")
    print("Note: This requires PulseAudio")
    
    try:
        while True:
            try:
                result = subprocess.run(['pactl', 'list', 'sink-inputs'],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                for line in result.stdout.splitlines():
                    if 'Sample Specification' in line:
                        spec = line.split(':')[1].strip()
                        parts = spec.split()
                        if len(parts) > 2:
                            rate = parts[2].replace("Hz", "")
                            print(f"\rCurrent sample rate: {rate} Hz", end='', flush=True)
                            break
                else:
                    print("\rNo audio stream detected", end='', flush=True)
                
                time.sleep(1)
            except Exception as e:
                print(f"\nError: {e}")
                break
    except KeyboardInterrupt:
        print("\n\nStopped monitoring")


# ============================================================================
# TOOL 14: SCALE IMAGE
# ============================================================================

def scale_image(input_path: Path, output: Path, w: int, h: int, mode: str):
    with Image.open(input_path) as img:
        ow, oh = img.size
        
        if mode == 'fit':
            if w and h:
                scale = min(w/ow, h/oh)
                size = (int(ow*scale), int(oh*scale))
            elif w:
                size = (w, int(w*oh/ow))
            elif h:
                size = (int(h*ow/oh), h)
            scaled = img.resize(size, Image.LANCZOS)
        elif mode == 'fill':
            scale = max(w/ow, h/oh)
            nw, nh = int(ow*scale), int(oh*scale)
            scaled = img.resize((nw, nh), Image.LANCZOS)
            l, t = (nw-w)//2, (nh-h)//2
            scaled = scaled.crop((l, t, l+w, t+h))
        elif mode == 'stretch':
            scaled = img.resize((w, h), Image.LANCZOS)
        
        output.parent.mkdir(parents=True, exist_ok=True)
        scaled.save(output)
        return scaled.size


# ============================================================================
# TOOL 15: SORT BY RESOLUTION
# ============================================================================

def organize_by_resolution(directory: Path):
    print("Scanning files...")
    images = FileScanner.scan_image(directory, False)
    videos = FileScanner.scan_video(directory, False)
    all_files = images + videos
    
    if not all_files:
        print("No media files found.")
        return
    
    print(f"Found {len(all_files)} files. Analyzing...")
    res_map = {}
    bucket = 200
    
    for f in all_files:
        try:
            if MediaExtensions.is_image(f):
                with Image.open(f) as img:
                    w, h = img.size
            elif MediaExtensions.is_video(f):
                r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                  '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x', str(f)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                if 'x' in r.stdout:
                    w, h = map(int, r.stdout.strip().split('x'))
                else:
                    continue
            else:
                continue
            
            bw = ((w + bucket - 1) // bucket) * bucket
            bh = ((h + bucket - 1) // bucket) * bucket
            key = f"{bw}x{bh}"
            
            if key not in res_map:
                res_map[key] = []
            res_map[key].append(f)
            print(f"  {f.name} -> {w}x{h} -> {key}")
        except Exception as e:
            print(f"  ERR {f.name}: {e}")
    
    print(f"\nOrganizing into {len(res_map)} groups...")
    for res, files in res_map.items():
        folder = directory / res
        folder.mkdir(exist_ok=True)
        for f in files:
            try:
                f.rename(folder / f.name)
            except Exception as e:
                print(f"ERR moving {f.name}: {e}")
    print("Done!")


# ============================================================================
# TOOL 16: MASS CROP IMAGES
# ============================================================================

def crop_images(files: List[Path], output: Path):
    output.mkdir(exist_ok=True)
    ok, none, fail = 0, 0, 0
    for f in files:
        try:
            with Image.open(f) as img:
                bg = Image.new(img.mode, img.size, img.getpixel((0, 0)))
                diff = ImageChops.difference(img, bg)
                diff = ImageChops.add(diff, diff, 2.0, -100)
                bbox = diff.getbbox()
                if bbox:
                    cropped = img.crop(bbox)
                    cropped.save(output / f.name)
                    print(f"OK {f.name}")
                    ok += 1
                else:
                    print(f"-- {f.name} (no border)")
                    none += 1
        except Exception as e:
            print(f"ERR {f.name}: {e}")
            fail += 1
    print(f"\nCropped: {ok} | No border: {none} | Failed: {fail}")


# ============================================================================
# TOOL 17: VIEW METADATA
# ============================================================================

def view_metadata(filepath: Path):
    print(f"\n{'='*60}")
    print(f"File: {filepath.name}")
    print('='*60)
    
    try:
        if MediaExtensions.is_audio(filepath):
            meta = AudioMetadata(filepath)
            if meta.audio:
                for field in ['artist', 'album', 'title', 'genre', 'date', 'tracknumber']:
                    val = meta.get(field)
                    if val:
                        print(f"{field.title()}: {val}")
            
            # Get duration
            r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                              '-of', 'default=noprint_wrappers=1:nokey=1', str(filepath)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if r.returncode == 0:
                dur = float(r.stdout.strip())
                mins, secs = divmod(int(dur), 60)
                print(f"Duration: {mins:02d}:{secs:02d}")
        
        elif MediaExtensions.is_video(filepath):
            import json
            r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                              'stream=width,height,codec_name:format=duration',
                              '-of', 'json', str(filepath)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if r.returncode == 0:
                data = json.loads(r.stdout)
                if 'streams' in data:
                    for stream in data['streams']:
                        if 'width' in stream:
                            print(f"Resolution: {stream['width']}x{stream['height']}")
                        if 'codec_name' in stream:
                            print(f"Codec: {stream['codec_name']}")
                if 'format' in data and 'duration' in data['format']:
                    dur = float(data['format']['duration'])
                    mins, secs = divmod(int(dur), 60)
                    print(f"Duration: {mins:02d}:{secs:02d}")
    except Exception as e:
        print(f"Error: {e}")


# ============================================================================
# RECOVER DATE
# Forensic date recovery for files from dead/recovered drives.
# Renames files as MM-DD-YYYY_originalname.ext using the best date found.
# Year-only confidence uses 00-00-YYYY so uncertain files are identifiable.
#
# Strategies (in priority order):
#  1. EXIF DateTimeOriginal / DateTimeDigitized
#  2. Embedded thumbnail EXIF (survives many stripping tools)
#  3. XMP metadata block (survives independently of EXIF)
#  4. MakerNotes raw scan (Canon/Nikon/Apple/Sony date strings)
#  5. Filename-embedded date patterns
#  6. Video container atoms (MP4 mvhd, AVI IDIT)
#  7. Audio ID3 / mutagen tags
#  8. PDF CreationDate
#  9. Office Open-XML core properties
# 10. EXIF Model -> device release year floor
# 11. JPEG quantization table -> camera fingerprint floor
# 12. Filesystem timestamp (filtered: skips timestamps matching recovery date)
# 13. Drive-era fallback (last resort, year-only)
# ============================================================================

import io
import struct
import zipfile
from datetime import datetime, timedelta
from enum import IntEnum

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from hachoir.parser import createParser
    from hachoir.metadata import extractMetadata
    HAS_HACHOIR = True
except ImportError:
    HAS_HACHOIR = False

try:
    from PIL.ExifTags import TAGS as EXIF_TAGS
    HAS_EXIF_TAGS = True
except ImportError:
    HAS_EXIF_TAGS = False


class DatePrecision(IntEnum):
    UNKNOWN = 0
    YEAR    = 1
    MONTH   = 2
    FULL    = 3


class DateResult:
    def __init__(self, dt: datetime, precision: DatePrecision, source: str):
        self.dt        = dt
        self.precision = precision
        self.source    = source

    def prefix(self) -> str:
        """Return the filename prefix: MM-DD-YYYY or 00-00-YYYY for year-only."""
        if self.precision == DatePrecision.FULL:
            return self.dt.strftime("%m-%d-%Y")
        elif self.precision == DatePrecision.MONTH:
            return self.dt.strftime("%m-00-%Y")
        else:
            return f"00-00-{self.dt.year}"


# Device database: (substring_in_make_model_lower, release_year, latest_year, label)
# Sorted longest-first so "iphone 6s" matches before "iphone 6"
_DEVICE_DB = [
    ("iphone 3gs",        2009, 2011, "iPhone 3GS"),
    ("iphone 3g",         2008, 2010, "iPhone 3G"),
    ("iphone 4s",         2011, 2013, "iPhone 4S"),
    ("iphone 4",          2010, 2012, "iPhone 4"),
    ("iphone 5s",         2013, 2015, "iPhone 5S"),
    ("iphone 5c",         2013, 2015, "iPhone 5C"),
    ("iphone 5",          2012, 2014, "iPhone 5"),
    ("iphone 6 plus",     2014, 2016, "iPhone 6 Plus"),
    ("iphone 6s plus",    2015, 2017, "iPhone 6S Plus"),
    ("iphone 6s",         2015, 2017, "iPhone 6S"),
    ("iphone 6",          2014, 2016, "iPhone 6"),
    ("iphone se",         2016, 2020, "iPhone SE"),
    ("iphone 7 plus",     2016, 2018, "iPhone 7 Plus"),
    ("iphone 7",          2016, 2018, "iPhone 7"),
    ("iphone 8 plus",     2017, 2019, "iPhone 8 Plus"),
    ("iphone 8",          2017, 2019, "iPhone 8"),
    ("iphone xs max",     2018, 2020, "iPhone XS Max"),
    ("iphone xs",         2018, 2020, "iPhone XS"),
    ("iphone xr",         2018, 2020, "iPhone XR"),
    ("iphone x",          2017, 2019, "iPhone X"),
    ("iphone 11 pro max", 2019, 2021, "iPhone 11 Pro Max"),
    ("iphone 11 pro",     2019, 2021, "iPhone 11 Pro"),
    ("iphone 11",         2019, 2021, "iPhone 11"),
    ("iphone 12 pro max", 2020, 2022, "iPhone 12 Pro Max"),
    ("iphone 12 pro",     2020, 2022, "iPhone 12 Pro"),
    ("iphone 12 mini",    2020, 2022, "iPhone 12 Mini"),
    ("iphone 12",         2020, 2022, "iPhone 12"),
    ("iphone 13 pro max", 2021, 2023, "iPhone 13 Pro Max"),
    ("iphone 13 pro",     2021, 2023, "iPhone 13 Pro"),
    ("iphone 13 mini",    2021, 2023, "iPhone 13 Mini"),
    ("iphone 13",         2021, 2023, "iPhone 13"),
    ("iphone 14 pro max", 2022, 2024, "iPhone 14 Pro Max"),
    ("iphone 14 pro",     2022, 2024, "iPhone 14 Pro"),
    ("iphone 14",         2022, 2024, "iPhone 14"),
    ("iphone 15 pro max", 2023, 2026, "iPhone 15 Pro Max"),
    ("iphone 15 pro",     2023, 2026, "iPhone 15 Pro"),
    ("iphone 15",         2023, 2026, "iPhone 15"),
    ("iphone 16",         2024, 2027, "iPhone 16"),
    ("sm-g920",  2015, 2017, "Samsung S6"),
    ("sm-g930",  2016, 2018, "Samsung S7"),
    ("sm-g935",  2016, 2018, "Samsung S7 Edge"),
    ("sm-g950",  2017, 2019, "Samsung S8"),
    ("sm-g960",  2018, 2020, "Samsung S9"),
    ("sm-g970",  2019, 2021, "Samsung S10e"),
    ("sm-g973",  2019, 2021, "Samsung S10"),
    ("sm-g975",  2019, 2021, "Samsung S10+"),
    ("sm-g980",  2020, 2022, "Samsung S20"),
    ("sm-g991",  2021, 2023, "Samsung S21"),
    ("sm-s901",  2022, 2024, "Samsung S22"),
    ("sm-s911",  2023, 2025, "Samsung S23"),
    ("sm-s921",  2024, 2026, "Samsung S24"),
    ("galaxy s6", 2015, 2017, "Samsung Galaxy S6"),
    ("galaxy s7", 2016, 2018, "Samsung Galaxy S7"),
    ("galaxy s8", 2017, 2019, "Samsung Galaxy S8"),
    ("galaxy s9", 2018, 2020, "Samsung Galaxy S9"),
    ("galaxy s10",2019, 2021, "Samsung Galaxy S10"),
    ("galaxy s20",2020, 2022, "Samsung Galaxy S20"),
    ("galaxy s21",2021, 2023, "Samsung Galaxy S21"),
    ("galaxy s22",2022, 2024, "Samsung Galaxy S22"),
    ("galaxy s23",2023, 2025, "Samsung Galaxy S23"),
    ("galaxy s24",2024, 2026, "Samsung Galaxy S24"),
    ("pixel 2 xl",  2017, 2019, "Pixel 2 XL"),
    ("pixel 2",     2017, 2019, "Pixel 2"),
    ("pixel 3a",    2019, 2021, "Pixel 3a"),
    ("pixel 3 xl",  2018, 2020, "Pixel 3 XL"),
    ("pixel 3",     2018, 2020, "Pixel 3"),
    ("pixel 4 xl",  2019, 2021, "Pixel 4 XL"),
    ("pixel 4a",    2020, 2022, "Pixel 4a"),
    ("pixel 4",     2019, 2021, "Pixel 4"),
    ("pixel 5",     2020, 2022, "Pixel 5"),
    ("pixel 6 pro", 2021, 2023, "Pixel 6 Pro"),
    ("pixel 6",     2021, 2023, "Pixel 6"),
    ("pixel 7 pro", 2022, 2024, "Pixel 7 Pro"),
    ("pixel 7",     2022, 2024, "Pixel 7"),
    ("pixel 8 pro", 2023, 2025, "Pixel 8 Pro"),
    ("pixel 8",     2023, 2025, "Pixel 8"),
    ("pixel 9",     2024, 2026, "Pixel 9"),
    ("canon eos 5d mark iv",  2016, 2099, "Canon 5D Mk IV"),
    ("canon eos 5d mark iii", 2012, 2018, "Canon 5D Mk III"),
    ("canon eos 5d mark ii",  2008, 2014, "Canon 5D Mk II"),
    ("canon eos 6d mark ii",  2017, 2099, "Canon 6D Mk II"),
    ("canon eos 6d",          2012, 2018, "Canon 6D"),
    ("canon eos 90d",         2019, 2099, "Canon 90D"),
    ("canon eos 80d",         2016, 2021, "Canon 80D"),
    ("canon eos 70d",         2013, 2018, "Canon 70D"),
    ("canon eos r5",          2020, 2099, "Canon EOS R5"),
    ("canon eos r6",          2020, 2099, "Canon EOS R6"),
    ("canon eos r",           2018, 2099, "Canon EOS R"),
    ("nikon d850",  2017, 2099, "Nikon D850"),
    ("nikon d810",  2014, 2019, "Nikon D810"),
    ("nikon d800",  2012, 2017, "Nikon D800"),
    ("nikon d750",  2014, 2020, "Nikon D750"),
    ("nikon d7500", 2017, 2099, "Nikon D7500"),
    ("nikon d7200", 2015, 2019, "Nikon D7200"),
    ("nikon d3500", 2018, 2099, "Nikon D3500"),
    ("nikon z6",    2018, 2099, "Nikon Z6"),
    ("nikon z7",    2018, 2099, "Nikon Z7"),
    ("ilce-7m3",    2018, 2099, "Sony A7 III"),
    ("ilce-7m2",    2014, 2020, "Sony A7 II"),
    ("ilce-7rm4",   2019, 2099, "Sony A7R IV"),
    ("ilce-7rm3",   2017, 2099, "Sony A7R III"),
    ("ilce-6400",   2019, 2099, "Sony A6400"),
    ("ilce-6300",   2016, 2020, "Sony A6300"),
    ("gopro hero 12", 2023, 2099, "GoPro Hero 12"),
    ("gopro hero 11", 2022, 2099, "GoPro Hero 11"),
    ("gopro hero 10", 2021, 2099, "GoPro Hero 10"),
    ("gopro hero 9",  2020, 2099, "GoPro Hero 9"),
    ("gopro hero 8",  2019, 2099, "GoPro Hero 8"),
    ("gopro hero 7",  2018, 2099, "GoPro Hero 7"),
    ("gopro hero 6",  2017, 2099, "GoPro Hero 6"),
    ("dji",           2012, 2099, "DJI Camera"),
]

# QT fingerprint DB: (first_16_luma_values, release_year, latest_year, label)
_QT_DB = [
    ((2,1,1,2,2,4,5,6,1,1,1,2,3,6,6,6),    1992, 2099, "IJG q95"),
    ((3,2,2,3,5,8,10,12,2,2,3,4,5,12,12,11),1992, 2099, "IJG q90"),
    ((4,3,3,4,5,8,10,12,3,3,4,5,7,12,12,11),1992, 2099, "IJG q85/WhatsApp"),
    ((6,4,4,6,10,16,20,24,5,5,6,8,13,24,22,18),1992,2099,"IJG q80"),
    ((8,6,6,8,12,20,26,31,6,6,7,10,17,29,28,22),1992,2099,"IJG q75"),
    ((16,11,10,16,24,40,51,61,12,12,14,19,26,58,60,55), 2010, 2013, "iPhone 4/iOS4-5"),
    ((2,2,2,2,3,4,5,6,2,2,2,2,3,4,5,6),    2014, 2016, "iPhone 6/iOS8-9"),
    ((2,2,2,2,3,3,4,5,2,2,2,2,3,3,4,5),    2016, 2019, "iPhone 7-8/iOS10-12"),
    ((1,1,1,1,2,2,3,3,1,1,1,1,2,2,3,3),    2019, 2099, "iPhone 11+/iOS13+"),
    ((4,3,3,4,6,10,13,16,3,3,3,4,6,10,13,16),2016,2018,"Samsung S7/S8"),
    ((3,2,2,3,5,8,10,12,2,2,2,3,5,8,10,12), 2018, 2021, "Samsung S9-S21"),
    ((2,1,1,2,2,3,3,4,1,1,1,2,2,3,3,4),    2018, 2099, "Google Pixel 3+"),
    ((1,1,1,1,1,2,2,2,1,1,1,1,1,2,2,2),    2005, 2099, "Canon EOS DSLR"),
    ((2,1,1,2,3,5,6,7,1,1,2,2,3,5,6,5),    2005, 2099, "Nikon DSLR"),
    ((3,2,2,3,5,8,10,12,2,2,3,4,5,12,12,11),2013,2099, "Sony mirrorless"),
]


class RecoverDate:
    """
    Forensic date recovery — finds the best available date for each file
    and renames it as MM-DD-YYYY_originalname.ext.
    Year-only confidence: 00-00-YYYY_originalname.ext
    """

    MIN_YEAR = 1990
    MAX_YEAR = datetime.now().year

    IMAGE_EXTS = {'.jpg','.jpeg','.tif','.tiff','.png','.heic','.heif',
                  '.webp','.cr2','.nef','.arw','.orf','.rw2','.dng','.raw'}
    VIDEO_EXTS = {'.mp4','.m4v','.mov','.3gp','.avi','.mkv','.wmv','.flv'}
    AUDIO_EXTS = {'.mp3','.m4a','.aac','.flac','.ogg','.opus','.wma','.wav','.aiff'}
    OFFICE_EXTS= {'.docx','.xlsx','.pptx','.odt','.ods','.odp'}

    def __init__(self):
        self.recovery_date: Optional[datetime] = None
        self.drive_year_min: int = self.MIN_YEAR
        self.drive_year_max: int = self.MAX_YEAR
        self.stats = {'renamed': 0, 'skipped': 0, 'failed': 0}

    # ── helpers ───────────────────────────────────────────────────────────────

    def _sane(self, dt: Optional[datetime]) -> Optional[datetime]:
        if dt and self.MIN_YEAR <= dt.year <= self.MAX_YEAR:
            return dt
        return None

    def _parse_dt(self, s: str) -> Optional[datetime]:
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s.strip()[:19], fmt)
            except (ValueError, AttributeError):
                pass
        return None

    def _lookup_device(self, make: str, model: str) -> Optional[Tuple[int, int, str]]:
        combined = (make + " " + model).lower()
        for needle, ry, ly, label in _DEVICE_DB:
            if needle in combined:
                return (ry, ly, label)
        return None

    def _extract_luma_qt(self, data: bytes) -> Optional[tuple]:
        i = 0
        while i < len(data) - 4:
            if data[i] != 0xFF:
                i += 1; continue
            marker = data[i+1]
            if marker == 0xD8: i += 2; continue
            if marker in (0xD9, 0xDA): break
            if i + 3 >= len(data): break
            length = struct.unpack_from(">H", data, i+2)[0]
            if marker == 0xDB:
                offset, end = i + 4, i + 2 + length
                while offset + 65 <= end:
                    qt_info = data[offset]
                    precision, table_id = qt_info >> 4, qt_info & 0x0F
                    if precision == 0:
                        if table_id == 0:
                            return tuple(data[offset+1: offset+65])
                        offset += 65
                    else:
                        if table_id == 0:
                            return tuple(struct.unpack_from(">64H", data, offset+1))
                        offset += 129
            i += 2 + length
        return None

    def _match_qt(self, qt: tuple) -> Optional[Tuple[int, int, str]]:
        if not qt or len(qt) < 16:
            return None
        fp = qt[:16]
        best, best_score = None, -1
        for db_fp, ry, ly, label in _QT_DB:
            score = sum(1 for a, b in zip(fp, db_fp) if a == b)
            if score > best_score:
                best_score, best = score, (ry, ly, label)
        return best if best and best_score >= 12 else None

    # ── individual strategies ─────────────────────────────────────────────────

    def _exif(self, path: Path) -> Tuple[Optional[datetime], Optional[str], Optional[str]]:
        try:
            img = Image.open(path)
            raw = img._getexif() or {}
            tagged = {EXIF_TAGS.get(k, k): v for k, v in raw.items()} if HAS_EXIF_TAGS else {}
            dt = None
            for field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                rv = tagged.get(field)
                if rv:
                    dt = self._sane(self._parse_dt(str(rv)))
                    if dt:
                        break
            make  = str(tagged.get("Make",  "") or "").strip() or None
            model = str(tagged.get("Model", "") or "").strip() or None
            return dt, make, model
        except Exception:
            return None, None, None

    def _thumbnail_exif(self, path: Path) -> Optional[datetime]:
        try:
            img = Image.open(path)
            exif_raw = img.info.get("exif", b"")
            thumb_start = exif_raw.find(b'\xff\xd8', 6)
            if thumb_start == -1:
                return None
            thumb = Image.open(io.BytesIO(exif_raw[thumb_start:]))
            raw = thumb._getexif() or {}
            tagged = {EXIF_TAGS.get(k, k): v for k, v in raw.items()} if HAS_EXIF_TAGS else {}
            for field in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
                rv = tagged.get(field)
                if rv:
                    dt = self._sane(self._parse_dt(str(rv)))
                    if dt:
                        return dt
        except Exception:
            pass
        return None

    def _xmp(self, path: Path) -> Optional[datetime]:
        _re = re.compile(
            rb'(?:xmp:CreateDate|xmp:ModifyDate|photoshop:DateCreated|'
            rb'xmpMM:CreateDate|exif:DateTimeOriginal)[^>]*>([^<]{10,25})<',
            re.IGNORECASE
        )
        try:
            with open(path, 'rb') as f:
                data = f.read(131072)
            start = data.find(b'<xpacket')
            if start == -1:
                start = data.find(b'<?xpacket')
            if start == -1:
                return None
            end = data.find(b'</xmpmeta>', start)
            block = data[start: end+200] if end != -1 else data[start: start+65536]
            for m in _re.finditer(block):
                dt = self._sane(self._parse_dt(m.group(1).decode(errors='ignore').strip()))
                if dt:
                    return dt
        except Exception:
            pass
        return None

    def _makernotes(self, path: Path) -> Optional[datetime]:
        _re = re.compile(
            rb'(\d{4})[:\-/](\d{2})[:\-/](\d{2})[T ](\d{2}):(\d{2}):(\d{2})'
        )
        try:
            with open(path, 'rb') as f:
                data = f.read(min(524288, os.path.getsize(path)))
            for m in _re.finditer(data):
                try:
                    dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                  int(m.group(4)), int(m.group(5)), int(m.group(6)))
                    if self._sane(dt):
                        return dt
                except ValueError:
                    pass
        except Exception:
            pass
        return None

    def _filename(self, path: Path) -> Tuple[Optional[datetime], DatePrecision]:
        patterns = [
            (r'(?:IMG|VID|DSC|DCIM|PIC|MOV|PICT|photo)[_\-]?(\d{4})(\d{2})(\d{2})', 1, 2, 3),
            (r'(\d{4})[_\-](\d{2})[_\-](\d{2})', 1, 2, 3),
            (r'(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)',1, 2, 3),
            (r'[Ss]creenshot[_\- ](\d{4})[_\-](\d{2})[_\-](\d{2})', 1, 2, 3),
            (r'WhatsApp\s+\w+\s+(\d{4})-(\d{2})-(\d{2})', 1, 2, 3),
            (r'(?:^|[_\-\s(])(\d{4})(?:$|[_\-\s)])', 1, None, None),
        ]
        for pat, yi, mi, di in patterns:
            m = re.search(pat, path.stem)
            if not m:
                continue
            try:
                year  = int(m.group(yi))
                month = int(m.group(mi)) if mi else 1
                day   = int(m.group(di)) if di else 1
                if not (1 <= month <= 12 and 1 <= day <= 31):
                    continue
                dt = datetime(year, month, day)
                if not self._sane(dt):
                    continue
                if mi and di:
                    return dt, DatePrecision.FULL
                elif mi:
                    return dt, DatePrecision.MONTH
                else:
                    return dt, DatePrecision.YEAR
            except (ValueError, IndexError):
                pass
        return None, DatePrecision.UNKNOWN

    def _video_container(self, path: Path) -> Optional[datetime]:
        try:
            with open(path, 'rb') as f:
                data = f.read(min(2097152, os.path.getsize(path)))
            ext = path.suffix.lower()
            if ext in ('.mp4', '.m4v', '.mov', '.m4a', '.3gp'):
                QT_EPOCH = datetime(1904, 1, 1)
                idx = 0
                while idx < len(data) - 8:
                    size = struct.unpack_from(">I", data, idx)[0]
                    if data[idx+4:idx+8] == b'mvhd' and size >= 24:
                        v = data[idx+8]
                        secs = struct.unpack_from(">I", data, idx+12)[0] if v == 0 \
                               else struct.unpack_from(">Q", data, idx+12)[0]
                        if secs > 0:
                            return self._sane(QT_EPOCH + timedelta(seconds=int(secs)))
                    if size < 8: break
                    idx += size
            elif ext == '.avi':
                idx = data.find(b'IDIT')
                if idx != -1:
                    sz  = struct.unpack_from("<I", data, idx+4)[0]
                    raw = data[idx+8: idx+8+sz].decode(errors='ignore').strip('\x00').strip()
                    for fmt in ("%a %b %d %H:%M:%S %Y", "%Y-%m-%d %H:%M:%S"):
                        try:
                            return self._sane(datetime.strptime(raw[:24], fmt))
                        except ValueError:
                            pass
        except Exception:
            pass
        return None

    def _audio_tag(self, path: Path) -> Optional[datetime]:
        try:
            f = MutagenFile(path, easy=True)
            if not f:
                return None
            for key in ('date', 'year', 'originaldate', 'tdrc', 'tyer'):
                val = f.get(key)
                if val:
                    raw = str(val[0]).strip()[:10]
                    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y"):
                        try:
                            return self._sane(datetime.strptime(raw, fmt))
                        except ValueError:
                            pass
        except Exception:
            pass
        return None

    def _pdf(self, path: Path) -> Optional[datetime]:
        _re = re.compile(rb"D:(\d{4})(\d{2})(\d{2})")
        if HAS_PYMUPDF:
            try:
                doc = fitz.open(str(path))
                for key in ('creationDate', 'modDate'):
                    raw = doc.metadata.get(key, '')
                    if raw:
                        m = re.match(r"D:(\d{4})(\d{2})(\d{2})", raw.strip())
                        if m:
                            return self._sane(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))))
            except Exception:
                pass
        try:
            with open(path, 'rb') as f:
                data = f.read(min(65536, os.path.getsize(path)))
            m = _re.search(data)
            if m:
                return self._sane(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except Exception:
            pass
        return None

    def _office(self, path: Path) -> Optional[datetime]:
        _re = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
        try:
            with zipfile.ZipFile(path) as z:
                if 'docProps/core.xml' not in z.namelist():
                    return None
                xml = z.read('docProps/core.xml').decode(errors='ignore')
                for tag in ('dcterms:created', 'dcterms:modified', 'dc:date'):
                    m = re.search(rf'<{tag}[^>]*>([^<]+)<', xml)
                    if m:
                        dm = _re.search(m.group(1))
                        if dm:
                            return self._sane(datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3))))
        except Exception:
            pass
        return None

    def _filesystem(self, path: Path) -> Optional[datetime]:
        try:
            stat = path.stat()
            candidates = [stat.st_mtime]
            if hasattr(stat, 'st_birthtime'):
                candidates.append(stat.st_birthtime)
            candidates.append(stat.st_ctime)
            for ts in candidates:
                if ts <= 0:
                    continue
                dt = datetime.fromtimestamp(ts)
                if not self._sane(dt):
                    continue
                if self.recovery_date is not None:
                    if abs((dt.date() - self.recovery_date.date()).days) <= 1:
                        continue   # poisoned — stamped during recovery
                return dt
        except Exception:
            pass
        return None

    # ── master resolver ───────────────────────────────────────────────────────

    def resolve(self, path: Path) -> DateResult:
        ext  = path.suffix.lower()
        make = model = None

        # 1. EXIF DateTimeOriginal
        if ext in self.IMAGE_EXTS | self.VIDEO_EXTS:
            dt, make, model = self._exif(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "EXIF DateTimeOriginal")

        # 2. Embedded thumbnail EXIF
        if ext in self.IMAGE_EXTS:
            dt = self._thumbnail_exif(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "Thumbnail EXIF")

        # 3. XMP block
        if ext in self.IMAGE_EXTS | {'.pdf', '.ai', '.eps'}:
            dt = self._xmp(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "XMP metadata")

        # 4. MakerNotes raw scan
        if ext in self.IMAGE_EXTS:
            dt = self._makernotes(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "MakerNotes")

        # 5. Filename (save partial result)
        fname_dt, fname_prec = self._filename(path)
        if fname_dt and fname_prec == DatePrecision.FULL:
            return DateResult(fname_dt, DatePrecision.FULL, "Filename")

        # 6. Video container
        if ext in self.VIDEO_EXTS:
            dt = self._video_container(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "Video container")

        # 7. Audio tags
        if ext in self.AUDIO_EXTS:
            dt = self._audio_tag(path)
            if dt:
                return DateResult(dt, DatePrecision.YEAR, "Audio tag")

        # 8. PDF
        if ext == '.pdf':
            dt = self._pdf(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "PDF CreationDate")

        # 9. Office XML
        if ext in self.OFFICE_EXTS:
            dt = self._office(path)
            if dt:
                return DateResult(dt, DatePrecision.FULL, "Office XML")

        # 10 + 11. Device model / QT floor
        if ext in self.IMAGE_EXTS and make is None:
            _, make, model = self._exif(path)
        device_floor = self._lookup_device(make or "", model or "") if (make or model) else None

        qt_floor = None
        if ext in {'.jpg', '.jpeg'}:
            try:
                with open(path, 'rb') as f:
                    raw_bytes = f.read(min(65536, os.path.getsize(path)))
                qt = self._extract_luma_qt(raw_bytes)
                if qt:
                    qt_floor = self._match_qt(qt)
            except Exception:
                pass

        floor_low = floor_high = None
        floor_label = ""
        if device_floor:
            floor_low, floor_high, floor_label = device_floor
        if qt_floor:
            ql, qh, qlabel = qt_floor
            floor_low  = max(floor_low, ql)  if floor_low  is not None else ql
            floor_high = min(floor_high, qh) if floor_high is not None else qh
            floor_label += (f" + QT:{qlabel}" if floor_label else f"QT:{qlabel}")

        if floor_low is not None:
            floor_low  = max(floor_low,  self.drive_year_min)
            floor_high = min(floor_high, self.drive_year_max)
            if floor_low > floor_high:
                floor_low, floor_high = self.drive_year_min, self.drive_year_max

        # 12. Filesystem timestamp (cross-referenced against device floor)
        fs_dt = self._filesystem(path)
        if fs_dt:
            if floor_low is not None:
                if floor_low <= fs_dt.year <= floor_high:
                    return DateResult(fs_dt, DatePrecision.FULL,
                                      f"Filesystem (confirmed: {floor_label})")
                elif fs_dt.year < floor_low:
                    return DateResult(datetime(floor_low, 1, 1), DatePrecision.YEAR,
                                      f"Device floor: {floor_label} (FS impossible)")
                else:
                    return DateResult(fs_dt, DatePrecision.FULL,
                                      f"Filesystem (post-device: {floor_label})")
            return DateResult(fs_dt, DatePrecision.FULL, "Filesystem timestamp")

        # Floor without FS
        if floor_low is not None:
            if fname_dt and floor_low <= fname_dt.year <= floor_high:
                return DateResult(fname_dt, fname_prec,
                                  f"Filename (confirmed: {floor_label})")
            return DateResult(datetime(floor_low, 1, 1), DatePrecision.YEAR,
                              f"Device/QT floor: {floor_label} ({floor_low}-{floor_high})")

        # Filename partial
        if fname_dt:
            return DateResult(fname_dt, fname_prec, "Filename (partial)")

        # 13. Drive-era fallback
        return DateResult(datetime(self.drive_year_min, 1, 1), DatePrecision.YEAR,
                          f"Drive era fallback ({self.drive_year_min}-{self.drive_year_max})")

    # ── public entry point ────────────────────────────────────────────────────

    def run(self):
        directory = PathUtils.get_valid_path("Directory: ")

        # Recovery date
        print("\nRecovery date — when did you copy files off the dead drive?")
        print("Filesystem timestamps on this date are poisoned and will be skipped.")
        raw = input("Recovery date (YYYY-MM-DD, or blank to skip): ").strip()
        if raw:
            try:
                self.recovery_date = datetime.strptime(raw, "%Y-%m-%d")
                print(f"OK Timestamps within ±1 day of {self.recovery_date.date()} ignored.")
            except ValueError:
                print("Invalid format, skipping recovery date filter.")

        # Drive era
        print("\nDrive era — approximately when were files originally made?")
        print("Used as last-resort fallback. Leave blank to keep open.")
        for attr, label, default in [
            ('drive_year_min', 'Earliest year', self.MIN_YEAR),
            ('drive_year_max', 'Latest year',   self.MAX_YEAR),
        ]:
            while True:
                raw = input(f"{label} (default {default}): ").strip()
                if not raw:
                    setattr(self, attr, default)
                    break
                if raw.isdigit() and self.MIN_YEAR <= int(raw) <= self.MAX_YEAR:
                    setattr(self, attr, int(raw))
                    break
                print(f"Enter a year between {self.MIN_YEAR} and {self.MAX_YEAR}.")
        if self.drive_year_min > self.drive_year_max:
            self.drive_year_min, self.drive_year_max = self.drive_year_max, self.drive_year_min

        recursive = UserInput.yes_no("Recursive?")

        # Collect files
        all_exts = (MediaExtensions.IMAGE | MediaExtensions.VIDEO |
                    MediaExtensions.AUDIO | {'.pdf','.docx','.xlsx','.pptx'})
        files = FileScanner.scan(directory, all_exts, recursive)
        if not files:
            print("No media files found.")
            return

        # Preview
        print(f"\nFound {len(files)} file(s). Previewing first 5:\n")
        for path in files[:5]:
            result = self.resolve(path)
            print(f"  {path.name}")
            print(f"  -> {result.prefix()}_{path.name}  [{result.source}]\n")

        if not UserInput.yes_no(f"\nRename all {len(files)} files?"):
            return

        print()
        for path in files:
            try:
                result = self.resolve(path)
                prefix = result.prefix()

                # Skip if already prefixed with this date
                if path.stem.startswith(prefix):
                    print(f"SKIP {path.name} (already dated)")
                    self.stats['skipped'] += 1
                    continue

                new_name = f"{prefix}_{path.name}"
                new_path = path.parent / new_name

                # Handle collision
                if new_path.exists():
                    stem, i = path.stem, 1
                    while new_path.exists():
                        new_name = f"{prefix}_{stem}_{i}{path.suffix}"
                        new_path = path.parent / new_name
                        i += 1

                path.rename(new_path)
                print(f"OK  {path.name}")
                print(f"    -> {new_name}  [{result.source}]")
                self.stats['renamed'] += 1

            except Exception as e:
                print(f"ERR {path.name}: {e}")
                self.stats['failed'] += 1

        print(f"\nRenamed: {self.stats['renamed']} | Skipped: {self.stats['skipped']} | Failed: {self.stats['failed']}")


# ============================================================================
# MAIN MENU
# ============================================================================

def show_menu(cmds: List[str], sel: int):
    clear()
    print("\033[1m  Media Tools\033[0m")
    print("  -----------\n")
    for i, cmd in enumerate(cmds):
        if i == sel:
            print(f"\033[1m> {cmd}\033[0m\n")
        else:
            print(f"  {cmd}\n")


def run_command(cmd: str):
    clear()
    
    if cmd == "Change Volume":
        if not check_ffmpeg():
            print("Error: ffmpeg not found")
        else:
            p = PathUtils.get_valid_path("File or directory: ")
            inc = UserInput.choice("Volume:", {'1': 'Reduce', '2': 'Increase'}) == '2'
            pct = UserInput.number("Percentage (1-100): ", 1, 100)
            db = pct if inc else -pct
            files = [p] if p.is_file() else FileScanner.scan_audio(p, False)
            if files:
                out = PathUtils.ensure_output_dir(p.parent if p.is_file() else p)
                adjust_volume(files, db, out)
    
    elif cmd == "Compare Audio":
        f1 = PathUtils.get_valid_path("First audio file: ")
        f2 = PathUtils.get_valid_path("Second audio file: ")
        compare_audio_spectrograms(f1, f2)
    
    elif cmd == "Convert to Opus":
        if not check_ffmpeg():
            print("Error: ffmpeg not found")
        else:
            d = PathUtils.get_valid_path("Directory: ")
            files = FileScanner.scan_audio(d, False)
            if files:
                lossless = UserInput.yes_no("Lossless source (FLAC/WAV)?")
                out = PathUtils.ensure_output_dir(d, "Converted")
                convert_opus(files, lossless, out)
    
    elif cmd == "Generate Album Sections":
        d = PathUtils.get_valid_path("Directory: ")
        organize_by_disc(d)
    
    elif cmd == "Lossless Separator":
        f = PathUtils.get_valid_path("Lossless album file (.flac/.wav/.ape): ")
        split_lossless_album(f)
    
    elif cmd == "Mass Crop Images":
        d = PathUtils.get_valid_path("Directory: ")
        files = FileScanner.scan_image(d, False)
        if files:
            out = PathUtils.ensure_output_dir(d)
            crop_images(files, out)
    
    elif cmd == "Mass Thumbnail":
        d = PathUtils.get_valid_path("Audio directory: ")
        files = FileScanner.scan_audio(d, False)
        if files:
            thumb = PathUtils.get_valid_path("Thumbnail image: ")
            if MediaExtensions.is_image(thumb):
                add_thumbnails(files, thumb)
    
    elif cmd == "Recover Date":
        RecoverDate().run()

    elif cmd == "Remove Audio":
        if not check_ffmpeg():
            print("Error: ffmpeg not found")
        else:
            d = PathUtils.get_valid_path("Directory: ")
            files = FileScanner.scan_video(d, False)
            if files:
                out = PathUtils.ensure_output_dir(d)
                remove_video_audio(files, out)
    
    elif cmd == "Remove Metadata":
        d = PathUtils.get_valid_path("Directory: ")
        if UserInput.yes_no("WARNING: Modifies in-place. Continue?"):
            rec = UserInput.yes_no("Recursive?")
            imgs = FileScanner.scan_image(d, rec)
            vids = FileScanner.scan_video(d, rec)
            if imgs or vids:
                remove_metadata(imgs + vids)
    
    elif cmd == "Rotate Video":
        if not check_ffmpeg():
            print("Error: ffmpeg not found")
        else:
            d = PathUtils.get_valid_path("Directory: ")
            files = FileScanner.scan_video(d, False)
            if files:
                deg = int(UserInput.choice("Rotation:", {'90': '90deg', '180': '180deg', '270': '270deg'}))
                out = PathUtils.ensure_output_dir(d, "Rotated")
                rotate_videos(files, deg, out)
    
    elif cmd == "Sample Rate Detector":
        monitor_sample_rate()
    
    elif cmd == "Scale Image":
        f = PathUtils.get_valid_path("Image file: ")
        if MediaExtensions.is_image(f):
            with Image.open(f) as img:
                print(f"Original: {img.size[0]} x {img.size[1]}")
            mode = UserInput.choice("Mode:", {'1': 'Fit', '2': 'Fill', '3': 'Stretch'})
            mode = {'1': 'fit', '2': 'fill', '3': 'stretch'}[mode]
            if mode == 'fit':
                ws = input("Width (Enter to skip): ").strip()
                hs = input("Height (Enter to skip): ").strip()
                w = int(ws) if ws else None
                h = int(hs) if hs else None
            else:
                w = int(UserInput.number("Width: ", 1))
                h = int(UserInput.number("Height: ", 1))
            out_dir = PathUtils.ensure_output_dir(f.parent, "Scaled")
            out = out_dir / f"{f.stem}_scaled{f.suffix}"
            sz = scale_image(f, out, w, h, mode)
            print(f"Scaled to {sz[0]}x{sz[1]}")
            print(f"Saved: {out}")
    
    elif cmd == "Sort by Album":
        d = PathUtils.get_valid_path("Directory: ")
        MusicOrganizer(d).by_album()
    
    elif cmd == "Sort by Artist":
        d = PathUtils.get_valid_path("Directory: ")
        rec = UserInput.yes_no("Recursive?")
        MusicOrganizer(d).by_artist(rec)
    
    elif cmd == "Sort by Genre":
        d = PathUtils.get_valid_path("Directory: ")
        MusicOrganizer(d).by_genre()
    
    elif cmd == "Sort by Resolution":
        d = PathUtils.get_valid_path("Directory: ")
        organize_by_resolution(d)
    
    elif cmd == "View Metadata":
        p = PathUtils.get_valid_path("File or directory: ")
        if p.is_file():
            view_metadata(p)
        else:
            files = FileScanner.scan_audio(p, False) + FileScanner.scan_video(p, False)
            for f in files[:10]:  # Limit to first 10
                view_metadata(f)
            if len(files) > 10:
                print(f"\n... and {len(files)-10} more files")
    
    elif cmd == "Quit":
        clear()
        print("\n\033[1mExiting\033[0m")
        sys.exit(0)
    
    input("\nPress Enter to continue...")


def main():
    cmds = [
        "Change Volume",
        "Compare Audio",
        "Convert to Opus",
        "Generate Album Sections",
        "Lossless Separator",
        "Mass Crop Images",
        "Mass Thumbnail",
        "Recover Date",
        "Remove Audio",
        "Remove Metadata",
        "Rotate Video",
        "Sample Rate Detector",
        "Scale Image",
        "Sort by Album",
        "Sort by Artist",
        "Sort by Genre",
        "Sort by Resolution",
        "View Metadata",
        "Quit"
    ]
    
    sel = 0
    while True:
        show_menu(cmds, sel)
        key = get_key()
        if key == 'UP':
            sel = (sel - 1) % len(cmds)
        elif key == 'DOWN':
            sel = (sel + 1) % len(cmds)
        elif key == 'ENTER':
            run_command(cmds[sel])
        elif key == 'CTRL_C':
            clear()
            print("\n\033[1mExiting\033[0m")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear()
        print("\n\033[1mExiting\033[0m")
