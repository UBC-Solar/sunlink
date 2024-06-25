import logging
import time
from datetime import datetime
import sys

# Custom handler for logging to work with updating time display
class TimeLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET):
        super().__init__(level)

    def emit(self, record):
        try:
            msg = self.format(record)
            sys.stdout.write("\033[K")  # Clear to the end of line
            sys.stdout.write(f"\r{msg}\n")
            self.flush()
        except Exception:
            self.handleError(record)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

handler = TimeLoggingHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def display_time():
    while True:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sys.stdout.write("\0337")  # Save cursor position
        sys.stdout.write(f"\033[1;33m{current_time}\033[0m")  # Yellow text
        sys.stdout.write("\0338")  # Restore cursor position
        sys.stdout.flush()
        time.sleep(0.001)

# Example of a function that logs messages and displays time
def install_package(total_steps):
    for i in range(total_steps):
        # Simulate a task
        time.sleep(0.1)
        # Log status messages
        logger.info(f"Completed step {i + 1}/{total_steps}")

if __name__ == "__main__":
    import threading

    # Start the time display in a separate thread
    time_thread = threading.Thread(target=display_time, daemon=True)
    time_thread.start()

    # Run the install package function
    install_package(100)
