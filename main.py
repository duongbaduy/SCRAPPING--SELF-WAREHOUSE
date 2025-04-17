# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import messagebox
import logging
import logging.handlers  # For RotatingFileHandler
import os
import sys       # To check platform (for macOS specific code)
import traceback # For detailed error logging

# --- Constants ---
APP_NAME = "ScraperApp" # Define your application name here
# Consider moving APP_NAME to config.py if you prefer

# --- Project Imports ---
# Assuming these files exist in the same directory or Python path
try:
    from gui import ScraperApp
    from config import DEBUG_LOG_FILENAME
except ImportError as e:
    print(f"Error importing project modules (gui, config): {e}")
    print("Please ensure gui.py and config.py are present and accessible.")
    # Provide default values if possible, otherwise the app might fail later
    if 'DEBUG_LOG_FILENAME' not in locals():
         DEBUG_LOG_FILENAME = f"{APP_NAME}_debug.log" # Use APP_NAME in default
    if 'ScraperApp' not in locals():
        # This is critical, display error and exit early if possible
        messagebox.showerror(
            "Startup Error",
            "Failed to load critical application component (ScraperApp).\n"
            f"Import Error: {e}\n\n"
            "Please ensure gui.py is present and correct.\n"
            "Check console output if running from terminal."
        )
        exit(1) # Exit if the core GUI class cannot be imported

# --- Main Execution Block ---
if __name__ == "__main__":

    # --- Determine Appropriate Log File Location ---
    log_dir = None
    try:
        if sys.platform == "darwin": # macOS
            # Standard macOS log location: ~/Library/Logs/YourAppName/
            log_dir = os.path.expanduser(f"~/Library/Logs/{APP_NAME}")
        elif sys.platform == "win32": # Windows
            # Common Windows location: %LOCALAPPDATA%\YourAppName\Logs
            local_app_data = os.getenv('LOCALAPPDATA')
            if local_app_data:
                log_dir = os.path.join(local_app_data, APP_NAME, "Logs")
            else: # Fallback if LOCALAPPDATA isn't set
                 log_dir = os.path.expanduser(f"~/.{APP_NAME}/logs")
        else: # Linux/Other Unix-like
            # Common Linux location: ~/.cache/YourAppName/logs or ~/.local/share/YourAppName/logs
            # Using a hidden directory in home as a simple default
            log_dir = os.path.expanduser(f"~/.{APP_NAME}/logs")

    except Exception as e:
        print(f"Warning: Error determining user-specific log directory: {e}")
        # Fallback to current directory or a sub-directory if needed
        log_dir = "logs" # Create a 'logs' subdir in the current dir

    # Use log filename from config or the default generated above
    log_filename_base = DEBUG_LOG_FILENAME
    log_filename = os.path.join(log_dir, log_filename_base)

    log_format = '%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s' # More detailed format
    log_level = logging.INFO # Change to logging.DEBUG for more verbose logs

    # --- Ensure Directory for Log File Exists ---
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True) # exist_ok=True avoids error if dir already exists
            print(f"Log directory created: {log_dir}")
        except OSError as e:
            print(f"Warning: Could not create log directory '{log_dir}'. Error: {e}")
            # Fallback: Log to the directory where the app is running (less ideal for packaged apps)
            log_filename = log_filename_base
            print(f"Warning: Logging fallback to: {os.path.abspath(log_filename)}")

    # --- Configure Logging ---
    try:
        # Use RotatingFileHandler for better log management
        # Keep 5 log files, max 5MB each. Adjust as needed.
        file_handler = logging.handlers.RotatingFileHandler(
            log_filename, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(log_format))

        # Get the root logger and add the handler
        # Set the root logger level; handlers can have their own levels too if needed
        logging.basicConfig(level=log_level, handlers=[file_handler])

        # Optional: Add console logging for immediate feedback *during development*
        # When packaged (especially with --windowed), console output might not be visible.
        # console_handler = logging.StreamHandler()
        # console_handler.setLevel(logging.INFO) # Set level for console
        # console_handler.setFormatter(logging.Formatter(log_format))
        # logging.getLogger('').addHandler(console_handler)

        print(f"Logging configured. Check file: {os.path.abspath(log_filename)}") # Useful for finding the log
        logging.info(f"--- {APP_NAME} Started ---")
        logging.info(f"Python Version: {sys.version}")
        logging.info(f"Platform: {sys.platform}")
        logging.info(f"Log file location: {log_filename}")

    except Exception as e:
        # Fallback to basic console logging if file setup fails
        print(f"CRITICAL: Error setting up file logging to '{log_filename}': {e}")
        print(traceback.format_exc())
        logging.basicConfig(level=log_level, format=log_format, encoding='utf-8')
        logging.error(f"File logging setup failed: {e}")
        logging.warning("Logging will proceed to console/default handler only.")

    # --- Initialize Tkinter ---
    root = None # Initialize root to None for better error handling
    try:
        root = tk.Tk()

        # --- Set macOS Specific App Name (Gracefully) ---
        if sys.platform == "darwin": # Only attempt on macOS
            try:
                # Attempt to set the app name shown in the main menu bar (Requires Tk 8.5+)
                # Uses Tcl command directly. Might fail on older/incomplete Tk installs.
                root.tk.call('tk::mac::setAppName', APP_NAME)
                logging.info(f"Set macOS menu bar app name to '{APP_NAME}'.")
            except tk.TclError:
                # Log a warning if the command fails, but don't stop the application
                logging.warning("Could not set macOS specific App Name in menu bar (tk::mac::setAppName command not available or failed in this Tk version). Using default.")

        # --- Set Window Title (Works on all platforms) ---
        root.title("Scraper Application") # Title shown in the window's title bar

        # --- Instantiate the Main Application Class ---
        # Ensure ScraperApp was imported successfully before trying to instantiate
        # (Import check already done near the top)
        app = ScraperApp(root) # Pass the root window to the app class

        # --- Handle Window Close Event (Top Right 'X' Button) ---
        def on_closing():
            """Handles the event when the user closes the window."""
            should_close = True # Assume we can close unless scraping is active
            # Check if 'app' exists and has the 'scraping_active' attribute
            if 'app' in locals() and hasattr(app, 'scraping_active') and app.scraping_active:
                if not messagebox.askokcancel("Quit", "Scraping is in progress. Are you sure you want to quit?\nThe process may stop abruptly."):
                    should_close = False # User cancelled closing
                else:
                    logging.warning("Application quit requested by user during active scraping.")
                    # Optional: Implement a graceful stop mechanism in ScraperApp
                    # if hasattr(app, 'stop_scraping_thread'):
                    #     logging.info("Attempting to signal scraping thread to stop...")
                    #     app.stop_scraping_thread() # Implement this method in ScraperApp
                    #     # You might want to wait a short period here or disable the close button
                    #     # until the thread confirms stoppage, but that adds complexity.
            else:
                # Log if closing when not scraping or if app object doesn't exist/have attribute
                 logging.debug("Window close request received (scraping not active or app state unknown).")


            if should_close:
                logging.info("Application window closing sequence initiated.")
                # The scraping thread (if running and daemonized) should exit when the main thread exits.
                # Non-daemon threads might block closing unless handled.
                root.destroy() # Close the Tkinter window and end mainloop

        root.protocol("WM_DELETE_WINDOW", on_closing) # Register the close handler

        # --- Start the GUI Event Loop ---
        logging.info("Starting Tkinter main event loop.")
        root.mainloop()
        # Code execution resumes here after root.destroy() is called

    except tk.TclError as e:
         # Catch specific Tkinter/Tcl errors (e.g., display issues, invalid commands)
         logging.critical(f"Fatal Tkinter TclError occurred: {e}", exc_info=True) # exc_info=True logs traceback
         print(f"Error: A critical problem occurred with the graphical interface ({e}). Check logs.")
         # Try to show a message box, but it might fail if Tk is broken
         try:
             messagebox.showerror("Fatal GUI Error", f"A critical problem occurred with the graphical interface:\n{e}\n\nCheck logs for details.\nLog location: {log_filename}")
         except Exception as msg_e:
             print(f"Could not display Tkinter error message box: {msg_e}")
    except Exception as e:
        # Catch any other unexpected errors during setup or runtime
        logging.critical(f"An unexpected fatal error occurred: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}. Check logs for details.")
        # Try to show a message box
        try:
             messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n{e}\n\nApplication must close.\nCheck logs for details.\nLog location: {log_filename}")
        except Exception as msg_e:
             print(f"Could not display general error message box: {msg_e}")
    finally:
        # This block executes whether the app closed normally or due to an error
        logging.info(f"--- {APP_NAME} Closed ---")
        # Check if root was successfully created before trying to destroy it again (in case of early exit)
        # Although mainloop exit usually means destroy was called, this is belt-and-suspenders
        # if root and root.winfo_exists():
        #    try:
        #        root.destroy() # Ensure window is gone if error happened before mainloop end
        #    except tk.TclError:
        #        pass # Window might already be destroyed

        print("Application has finished.")
        # No need to explicitly exit here unless there was a specific startup failure handled earlier