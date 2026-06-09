import re
from datetime import datetime, timedelta
from collections import defaultdict
import plotly.graph_objs as go
import plotly.io as pio
import os
import argparse
import math
import webbrowser
import numpy as np

from mexc_plot3i import process_log_file, get_timeline, parse_datetime  # Import the functions


def get_user_input(args):
    
    if args.format is None:
        print("Select data format:")
        print("1. New MEXC format")
        print("2. Old MEXC format")
        print("3. Kucoin format")
        format_choice = input("Enter your choice (1, 2, or 3): ")
        data_format = {'1': 'new_mexc', '2': 'old_mexc', '3': 'kucoin'}.get(format_choice, 'new_mexc')
    else:
        data_format = args.format

    if args.log_file is None and args.logs is None:
        while True:
            print("\nSelect log file:")
            print("1. Use default log (def.log)")
            print("2. Enter custom log name")
            choice = input("Enter your choice (1 or 2): ")

            if choice == '1':
                log_file = 'def.log'
            elif choice == '2':
                log_file = input("Enter the log file name: ")
            else:
                print("Invalid choice. Please try again.")
                continue

            pairs, coins, data = process_log_file(log_file, data_format)
            if data:
                break
            else:
                print(f"No valid data found in {log_file}. Please choose a different file.")
    else:
        log_file = args.log_file if args.log_file else args.logs[0]
        pairs, coins, data = process_log_file(log_file, data_format)

    if args.interval is None:
        print("\nSelect time interval:")
        print("1. 10 milliseconds")
        print("2. 100 milliseconds")
        print("3. 1 second")
        print("4. 10 seconds")
        print("5. 1 minute")
        print("6. 10 minutes")
        print("7. Custom interval")
        interval_choice = input("Enter your choice (1-7): ")

        if interval_choice == '7':
            interval_seconds = float(input("Enter custom interval in seconds (can be decimal, e.g., 0.01 for 10ms): "))
        else:
            interval_mapping = {'1': 0.01, '2': 0.1, '3': 1, '4': 10, '5': 60, '6': 600}
            interval_seconds = interval_mapping.get(interval_choice, 600)
    else:
        interval_seconds = args.interval

    log_start_time = min(entry[0] for entry in data)
    log_end_time = max(entry[0] for entry in data)

    if args.timeline:
        start_time, end_time = get_timeline(args.timeline, log_start_time, log_end_time)
    elif args.start_time and args.end_time:
        try:
            start_time = parse_datetime(args.start_time, data_format)
            end_time = parse_datetime(args.end_time, data_format)
            if start_time >= end_time:
                raise ValueError("Start time must be before end time.")
        except ValueError as e:
            print(f"Error with provided time range: {e}")
            print("Falling back to interactive timeline selection.")
            start_time = end_time = None
    else:
        start_time = end_time = None

    if start_time is None or end_time is None:
        print("\nSelect timeline:")
        print("1. All data from log")
        print("2. Custom timeframe")
        print("3. First 1 minute")
        print("4. First 2 minutes")
        print("5. First 10 minutes")
        print("6. First 1 hour")
        print("7. Last 1 minute")
        print("8. Last 15 minutes")
        print("9. Last 1 hour")
        timeline_choice = input("Enter your choice (1-9): ")

        if timeline_choice == '1':
            start_time, end_time = log_start_time, log_end_time
        elif timeline_choice == '2':
            while True:
                try:
                    start_str = input("Enter start time (YYYY-MM-DD HH:MM:SS.fff or YYYY-MM-DD HH:MM:SS,fff): ")
                    end_str = input("Enter end time (YYYY-MM-DD HH:MM:SS.fff or YYYY-MM-DD HH:MM:SS,fff): ")
                    start_time = parse_datetime(start_str, data_format)
                    end_time = parse_datetime(end_str, data_format)
                    if start_time < end_time:
                        break
                    else:
                        print("Start time must be before end time. Please try again.")
                except ValueError as e:
                    print(f"Invalid date format: {e}. Please try again.")
        else:
            timeline_mapping = {
                '3': 'first_1m', '4': 'first_2m', '5': 'first_10m', '6': 'first_1h',
                '7': 'last_1m', '8': 'last_15m', '9': 'last_1h'
            }
            timeline = timeline_mapping.get(timeline_choice, 'all')
            start_time, end_time = get_timeline(timeline, log_start_time, log_end_time)
            
    if args.volume_type is None:
        print("\nSelect volume type:")
        print("1. USDT")
        print("2. Coins")
        volume_choice = input("Enter your choice (1 or 2): ")
        volume_type = 'usdt' if volume_choice == '1' else 'coins'
    else:
        volume_type = args.volume_type

    if args.color_scheme is None:
        print("\nSelect color scheme:")
        print("1. Default (Blue, Orange, Red, Green)")
        print("2. Vibrant (Blue, Red, Green, Purple)")
        print("3. Monochrome (Black, Gray, Dark Gray, Light Gray)")
        print("4. Blue & Orange (Blue, Orange, Red, Green)")
        print("5. Purple & Cyan (Purple, Cyan, Orange, Green)")
        print("6. Magenta & Teal (Magenta, Teal, Orange, Navy)")
        print("7. Green & Red (Green, Red, Blue, Orange)")
        print("8. Brown & Sky Blue (Brown, Sky Blue, Pink, Lime)")
        print("9. Deep Sky Blue & Tomato (Deep Sky Blue, Tomato, Purple, Gold)")
        color_choice = input("Enter your choice (1-9): ")
        color_schemes = ['default', 'vibrant', 'monochrome', 'blue_orange', 'purple_cyan', 'magenta_teal', 'green_red', 'brown_skyblue', 'deepskyblue_tomato']
        color_scheme = color_schemes[int(color_choice) - 1]
    else:
        color_scheme = args.color_scheme

    if args.resolution is None:
        print("\nSelect resolution:")
        print("1. Default (1200x600)")
        print("2. Low (800x600)")
        print("3. Medium (1200x900)")
        print("4. High (1920x1080)")
        print("5. Ultra High (3840x2160)")
        print("6. Custom")
        resolution_choice = input("Enter your choice (1-6): ")
        resolutions = [(1200, 600), (800, 600), (1200, 900), (1920, 1080), (3840, 2160)]
        
        if resolution_choice == '6':
            custom_resolution = input("Enter custom resolution (width height, e.g., 1600 900): ")
            try:
                width, height = map(int, custom_resolution.split())
            except ValueError:
                print("Invalid input. Using default resolution (1200x600).")
                width, height = 1200, 600
        else:
            width, height = resolutions[int(resolution_choice) - 1]
    else:
        if args.resolution[0] == 'custom':
            if len(args.resolution) == 3:
                try:
                    width, height = map(int, args.resolution[1:])
                except ValueError:
                    print("Invalid custom resolution. Using default (1200x600).")
                    width, height = 1200, 600
            else:
                print("Custom resolution specified incorrectly. Using default (1200x600).")
                width, height = 1200, 600
        else:
            resolution_mapping = {
                'default': (1200, 600),
                'low': (800, 600),
                'medium': (1200, 900),
                'high': (1920, 1080),
                'ultra': (3840, 2160)
            }
            width, height = resolution_mapping.get(args.resolution[0], (1200, 600))

    if args.output_format is None:
        print("\nSelect output format:")
        print("1. Image")
        print("2. HTML")
        print("3. Both Image and HTML")
        print("4. Open in browser")
        output_choice = input("Enter your choice (1-4): ")
        output_formats = ['image', 'html', 'both', 'browser']
        output_format = output_formats[int(output_choice) - 1]
    else:
        output_format = args.output_format

    if output_format in ['image', 'both'] and args.image_format is None:
        print("\nSelect image format:")
        print("1. PNG")
        print("2. JPEG")
        print("3. SVG")
        print("4. PDF")
        print("5. WebP")
        image_format_choice = input("Enter your choice (1-5): ")
        image_formats = ['png', 'jpeg', 'svg', 'pdf', 'webp']
        image_format = image_formats[int(image_format_choice) - 1]
    else:
        image_format = args.image_format

    if args.background_color is None:
        print("\nSelect background color:")
        print("1. White")
        print("2. Very Light Blue")
        print("3. Very Light Yellow")
        print("4. Very Light Gray")
        bg_color_choice = input("Enter your choice (1-4): ")
        bg_colors = ['white', 'aliceblue', 'lightyellow', 'whitesmoke']
        bg_color = bg_colors[int(bg_color_choice) - 1]
    else:
        bg_color = args.background_color

    # Print summary of choices
    print("\nSummary of your choices:")
    print(f"Log file(s): {log_file if isinstance(log_file, str) else ', '.join(log_file)}")
    print(f"Data format: {data_format}")
    print(f"Time interval: {interval_seconds} seconds")
    print(f"Start time: {start_time}")
    print(f"End time: {end_time}")
    print(f"Volume type: {volume_type}")
    print(f"Color scheme: {color_scheme}")
    print(f"Resolution: {width}x{height}")
    print(f"Output format: {output_format}")
    if output_format in ['image', 'both']:
        print(f"Image format: {image_format}")
    print(f"Background color: {bg_color}")

    return log_file, interval_seconds, start_time, end_time, volume_type, color_scheme, output_format, width, height, image_format, data_format, bg_color
