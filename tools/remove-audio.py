import os
import subprocess

def remove_audio(input_dir, output_dir):
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Get list of video files in input directory
    video_files = [f for f in os.listdir(input_dir) if f.endswith(('.mp4', '.avi', '.webm', '.mov', '.mkv','.wmv'))]

    for video_file in video_files:
        input_path = os.path.join(input_dir, video_file)
        output_path = os.path.join(output_dir, video_file)

        # Run ffmpeg command to remove audio
        command = ['ffmpeg', '-i', input_path, '-c', 'copy', '-an', output_path]
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print("Audio removed from videos and saved in", output_dir)

if __name__ == "__main__":
    input_directory = input("Enter the directory: ")
    output_directory = os.path.join(input_directory, "Output")

    remove_audio(input_directory, output_directory)
