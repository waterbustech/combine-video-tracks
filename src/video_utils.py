import subprocess

def reencode_video(input_path, output_path):
    try:
        command = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', 'libx264',
            '-r', '15',
            '-c:a', 'aac',
            '-strict', 'experimental',
            '-b:a', '192k',
            '-async', '1',
            '-y',
            output_path
        ]

        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during re-encoding: {e.stderr.decode().strip()}")
        return False
