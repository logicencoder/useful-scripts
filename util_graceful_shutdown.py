import signal
import os
import threading
import logging
import sys

# Global variable to signal exit
exit_signal = threading.Event()

def exit_gracefully(signal_received, frame):
    """
    Handle the shutdown process when the program receives an interrupt or termination signal.
    """
    logging.info("Shutting down...")

    # Set the global exit signal to notify running threads or loops
    exit_signal.set()

    # Perform any additional cleanup if necessary (close files, connections, etc.)

    # Use os._exit to immediately terminate the interpreter if needed
    logging.info("Forcing shutdown now.")
    os._exit(0)

# Registering signals to catch interruptions and terminate events
if sys.platform != 'win32':
    signal.signal(signal.SIGTERM, exit_gracefully)
    signal.signal(signal.SIGINT, exit_gracefully)

# On Windows, you would have to use a slightly different method if needed.
