#!/usr/bin/env python3

import os
import subprocess

def convert_to_gif(input_file):
    """
    Converts a video file to a GIF using FFmpeg.

    Parameters:
    input_file (str): Path to the input video file.
    """
    try:
        # Get the base file name (without the extension)
        base_name = os.path.splitext(os.path.basename(input_file))[0]

        # Construct the output GIF file name
        output_file = f"{base_name}.gif"

        # Run the FFmpeg command to create a palette from the video
        subprocess.run([
            "ffmpeg",
            "-i", input_file,
            "-vf", "scale=320:-1,palettegen",
            "palette.png"
        ], check=True)

        # Run the FFmpeg command to convert the video to GIF without limiting frames
        subprocess.run([
            "ffmpeg",
            "-i", input_file,
            "-i", "palette.png",
            "-filter_complex", "scale=320:-1[x];[x][1:v]paletteuse",
            output_file
        ], check=True)

        print(f"Conversion complete. GIF saved to: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred during conversion: {e}")

# Get the input video file from the user
input_video = input("Enter the path to the input video file: ")

# Call the conversion function
convert_to_gif(input_video)
