# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import logging
import os
import traceback  # <--- Added import here

# --- Project Imports ---
# Assuming these files exist in the same directory or Python path
try:
    from gui import ScraperApp
    from config import DEBUG_LOG_FILENAME
except ImportError as e:
    print(f"Error importing project modules (gui, config): {e}")
    print("Please ensure gui.py and config.py are present and accessible.")
    # Optionally exit or provide default values if possible
    # For now, provide a default log filename if config import failed
    if 'DEBUG_LOG_FILENAME' not in locals():
         DEBUG_LOG_FILENAME = "scraper_debug.log"
    # If ScraperApp is critical, we might need to exit or handle this differently
    # For now, we'll let it potentially fail later during instantiation
    # exit(1)


# --- Main Execution Block ---
if __name__ == "__main__":
    # Set up basic logging to a file as well
    log_filename = DEBUG_LOG_FILENAME
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
    log_level = logging.INFO

    # Ensure directory for log file exists (if it's nested)
    log_dir = os.path.dirname(log_filename)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
            print(f"Log directory created: {log_dir}")
        except OSError as e:
            print(f"Warning: Could not create log directory '{log_dir}'. Logging to current directory. Error: {e}")
            log_filename = os.path.basename(log_filename) # Fallback to current dir

    # Configure file logging
    try:
        # Ensure exclusive access or handle potential sharing issues if needed
        logging.basicConfig(level=log_level,
                            format=log_format,
                            filename=log_filename,
                            filemode='w', # 'w' to overwrite each run, 'a' to append
                            encoding='utf-8') # Ensure UTF-8 encoding for the log file
        print(f"Debug logging enabled. Check file: {os.path.abspath(log_filename)}")
        logging.info("--- Scraper GUI Application Started ---")
    except Exception as e:
        print(f"Error setting up file logging to '{log_filename}': {e}")
        # Fallback to console logging if file setup fails
        logging.basicConfig(level=log_level, format=log_format)
        logging.error(f"File logging setup failed: {e}")
        logging.warning("Logging will proceed to console only.")


    # Optional: Add handler to root logger to also print INFO+ logs to console
    # This might be useful even if file logging works, for immediate feedback.
    # If basicConfig already set up a StreamHandler (e.g., during fallback),
    # this might add a duplicate console handler. Consider checking existing handlers.
    # console_handler = logging.StreamHandler()
    # console_handler.setLevel(logging.INFO) # Or desired level for console
    # formatter = logging.Formatter(log_format)
    # console_handler.setFormatter(formatter)
    # if not any(isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers):
    #      logging.getLogger('').addHandler(console_handler)


    # --- Initialize Tkinter ---
    try:
        root = tk.Tk()
        root.title("Scraper Application") # Give the window a title

        # Ensure ScraperApp was imported successfully before trying to instantiate
        if 'ScraperApp' in locals():
            app = ScraperApp(root) # Pass the root window to the app class
        else:
            # Handle the case where ScraperApp couldn't be imported
            logging.critical("ScraperApp class not found due to import error. Cannot start GUI.")
            messagebox.showerror("Startup Error", "Failed to load the main application component (ScraperApp).\nPlease check console/logs for import errors.")
            root.destroy() # Close the empty Tk window
            exit(1)       # Exit the script

        # --- Handle Window Close Event ---
        def on_closing():
            """Handles the event when the user closes the window."""
            should_close = True # Assume we can close unless scraping is active
            if hasattr(app, 'scraping_active') and app.scraping_active:
                if not messagebox.askokcancel("Quit", "Scraping is in progress. Are you sure you want to quit?\nThe process will stop abruptly."):
                    should_close = False # User cancelled closing
                else:
                    logging.warning("Application quit requested by user during scraping.")
                    # Optionally: Signal the scraping thread to stop gracefully if possible
                    # if hasattr(app, 'stop_scraping'):
                    #     app.stop_scraping() # Implement this method in ScraperApp if needed
            
            if should_close:
                logging.info("Application window closing.")
                # The scraping thread (if running and a daemon) will exit when the main thread exits.
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        # --- Start the GUI Event Loop ---
        root.mainloop()

    except tk.TclError as e:
         # Catch specific Tkinter errors, e.g., display issues
         logging.critical(f"Tkinter TclError occurred: {e}")
         logging.critical(traceback.format_exc())
         print(f"Error: A problem occurred with the graphical interface ({e}). Check logs.")
    except Exception as e:
        # Catch any other unexpected errors during setup or runtime
        logging.critical(f"An unexpected error occurred: {e}")
        logging.critical(traceback.format_exc())
        print(f"An unexpected error occurred: {e}. Check logs for details.")
    finally:
        logging.info("--- Scraper GUI Application Closed ---")