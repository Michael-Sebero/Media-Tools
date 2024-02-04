import os
import sys
import librosa
import matplotlib
matplotlib.use('Agg')  # Set the backend to 'Agg'
import matplotlib.pyplot as plt
import numpy as np
import librosa.display
from concurrent.futures import ThreadPoolExecutor
import warnings

def simple_progress_bar(iterable, length=20):
    total = len(iterable)
    progress = 0
    for item in iterable:
        yield item
        progress += 1
        percent = (progress / total) * 100
        count = int(length * progress // total)
        spaces = length - count
        sys.stdout.write("\r[{:#<{}}] {:.1f}%".format("#" * count, length, percent))
        sys.stdout.flush()
    sys.stdout.write("\n")

def plot_spectrogram(file_path, ax, title, duration=8*60):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        try:
            # Load only the specified duration of audio
            y, sr = librosa.load(file_path, duration=duration)
            D = librosa.amplitude_to_db(np.abs(librosa.stft(y)), ref=np.max)

            im = librosa.display.specshow(D, sr=sr, x_axis='time', y_axis='log', ax=ax)
            ax.set(title=title)
            plt.colorbar(im, ax=ax, format="%+2.0f dB")
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)

def compare_spectrograms(file_path1, file_path2):
    fig, axs = plt.subplots(2, 1, figsize=(10, 8))

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        # Submit tasks for parallel execution
        futures = [
            executor.submit(plot_spectrogram, file_path, ax, title)
            for file_path, ax, title in zip([file_path1, file_path2], axs, [os.path.basename(file_path1), os.path.basename(file_path2)])
        ]

        # Use a simple progress bar
        simple_progress_bar(futures)

    plt.tight_layout()

    # Get the path to the user's desktop
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

    # Save the comparison image to the desktop
    comparison_image_path = os.path.join(desktop_path, "comparison.png")

    try:
        # Save the plot without showing it
        plt.savefig(comparison_image_path)
        print(f"\nComparison image saved to: {comparison_image_path}")
    except Exception as e:
        print(f"Error saving comparison image: {e}", file=sys.stderr)

def main():
    try:
        file_path1 = input("Enter the path of the first audio file: ")
        file_path2 = input("Enter the path of the second audio file: ")

        print("\033[1mPlease wait...\033[0m")  # \033[1m for bold, \033[0m to reset formatting

        compare_spectrograms(file_path1, file_path2)
    except Exception as e:
        print(f"Error in main: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
