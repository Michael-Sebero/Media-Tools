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
