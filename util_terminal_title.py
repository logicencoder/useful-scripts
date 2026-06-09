import os
import sys

def set_terminal_title(title):
    """
    Set the terminal title in WSL2 Ubuntu.
    """
    sys.stdout.write(f"\x1b]0;{title}\x07")
    sys.stdout.flush()

def print_filename_in_title():
    """
    Print the current script's filename in the terminal title.
    """
    filename = os.path.basename(__file__)
    set_terminal_title(filename)
    print(f"The filename '{filename}' has been set as the terminal title.")

if __name__ == "__main__":
    print_filename_in_title()
    
    # Keep the script running to maintain the title
    input("Press Enter to exit...")




# version2

# import os
# # Add this right after the imports

# def set_terminal_title(title: str) -> None:
#     """Set the terminal window title."""
#     try:
#         if os.name == 'nt':  # Windows
#             os.system(f'title {title}')
#         else:  # Unix-like
#             print(f'\033]0;{title}\007', end='', flush=True)
#     except Exception as e:
#         logging.error(f"Failed to set terminal title: {e}")

# # Set title to current filename
# set_terminal_title(os.path.basename(__file__))