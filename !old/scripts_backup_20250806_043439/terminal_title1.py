import os
import sys


# =============== SET TERMINAL TITLE ===============

def set_terminal_title():
    """Set terminal title to the current script's filename"""
    # Get the script's filename without the path
    script_name = os.path.basename(sys.argv[0])
    
    # Set the terminal title using ANSI escape sequences (works in most terminals)
    if os.name == 'nt':  # Windows
        os.system(f"title {script_name}")
    else:  # macOS, Linux, etc.
        sys.stdout.write(f"\033]0;{script_name}\007")
        sys.stdout.flush()

# Call the function to set the title
set_terminal_title()