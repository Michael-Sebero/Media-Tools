import subprocess
import time

def get_sample_rate():
    try:
        # Run pactl command to get the current playback stream info
        result = subprocess.check_output(['pactl', 'list', 'sink-inputs'])
        result = result.decode('utf-8')

        # Find sample specification
        for line in result.splitlines():
            if 'Sample Specification' in line:
                sample_spec = line.split(':')[1].strip()
                # Extract the sample rate part from the specification (after the 'Hz')
                parts = sample_spec.split()
                if len(parts) > 2:
                    sample_rate = parts[2]  # This should be the sample rate, e.g., 96000Hz
                    return sample_rate.replace("Hz", "")  # Remove "Hz" for clean output
        return "No audio stream detected"
    except subprocess.CalledProcessError as e:
        print("Error while fetching audio data:", e)
        return None

def monitor_audio_sample_rate():
    print("Monitoring audio sample rate...")
    while True:
        sample_rate = get_sample_rate()
        if sample_rate:
            print(f"Current sample rate: {sample_rate} Hz")
        time.sleep(1)  # Check every second

if __name__ == "__main__":
    monitor_audio_sample_rate()
