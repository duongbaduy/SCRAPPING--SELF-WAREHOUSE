# gmaps_scraper_project/gui.py

# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import filedialog  # Explicit import for clarity
from tkinter import BooleanVar # Import BooleanVar
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.dialogs import Messagebox # Use ttkbootstrap's messagebox
import threading
import pandas as pd
import time
import random
import traceback
import os

# --- Project Imports ---
# Ensure config.py exists and has the variables
try:
    from config import CITIES, DEFAULT_OUTPUT_FILENAME
except ImportError:
    # Provide defaults if config.py is missing or doesn't define them
    print("WARN: config.py not found or missing definitions. Using defaults.")
    CITIES = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"]
    DEFAULT_OUTPUT_FILENAME = "gmaps_data_fallback.xlsx"

# Ensure scraper.py exists and has the function
try:
    from scraper import scrape_city
except ImportError:
    print("ERROR: scraper.py or the scrape_city function not found. GUI will load but scraping will fail.")
    # Define a dummy function to prevent immediate crash if scraper is missing
    def scrape_city(city, logger_callback):
        logger_callback(f"ERROR: Scraper function 'scrape_city' not found for {city}.", "ERROR")
        return [], "ERROR"

# --- Default Theme Options ---
DEFAULT_DARK_THEME = 'darkly'
DEFAULT_LIGHT_THEME = 'cosmo' # Or choose another like 'litera', 'lumen', 'flatly'

# --- Settings File ---
# ADD THIS: Define the path for the theme setting file
THEME_SETTINGS_FILE = "theme_setting.txt" # Simple file in the same directory

# --- GUI Application Class ---
class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Maps Scraper - Self Storage Australia")

        # --- START: Center the Window ---
        window_width = 800  # Kích thước cửa sổ mong muốn
        window_height = 750 # Kích thước cửa sổ mong muốn

        # Lấy kích thước màn hình
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Tính toán vị trí x, y để căn giữa
        center_x = int((screen_width / 2) - (window_width / 2))
        center_y = int((screen_height / 2) - (window_height / 2))

        # Đặt kích thước và vị trí cho cửa sổ
        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        # --- END: Center the Window ---

        # self.root.geometry("800x750") # Xóa hoặc comment dòng này đi
        self.root.minsize(700, 600) # Giữ lại minsize

        # --- Theme Loading ---
        saved_theme = self._load_theme_preference()
        is_dark_initially = (saved_theme == DEFAULT_DARK_THEME)

        self.dark_mode_var = BooleanVar(value=is_dark_initially)
        self.style = ttk.Style(theme=saved_theme)

        # --- Main Frame ---
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=BOTH, expand=YES)

        # Configure row/column weights for responsiveness
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(3, weight=1)

        # --- Header Frame ---
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        self.header_frame.columnconfigure(0, weight=1)
        self.header_frame.columnconfigure(1, weight=0)

        # --- Header Content ---
        self.title_label = ttk.Label(
            self.header_frame,
            text="Google Maps Scraper",
            font=("Helvetica", 20, "bold"),
            anchor="center"
        )
        self.title_label.grid(row=0, column=0, sticky="ew")

        self.subtitle_label = ttk.Label(
            self.header_frame,
            text="Self Storage Australia",
            font=("Helvetica", 12),
            bootstyle="secondary",
            anchor="center"
        )
        self.subtitle_label.grid(row=1, column=0, sticky="ew", pady=(0, 5))

        # --- Theme Toggle Button ---
        # ADD THIS: Set initial toggle text based on loaded theme
        initial_toggle_text = "🌙" if is_dark_initially else "☀️"
        self.theme_toggle = ttk.Checkbutton(
            self.header_frame,
            text=initial_toggle_text, # Set correct initial icon
            variable=self.dark_mode_var,
            command=self.toggle_theme,
            bootstyle="round-toggle",
        )
        self.theme_toggle.grid(row=0, column=1, rowspan=2, padx=(10, 0), pady=5, sticky="ne")

        # Optional: Separator line
        ttk.Separator(self.main_frame, orient=HORIZONTAL).grid(row=1, column=0, sticky="ew", pady=(0, 15))

        # --- Control Frame ---
        self.control_frame = ttk.LabelFrame(
            self.main_frame,
            text=" Settings & Actions ",
            padding=15,
            bootstyle=PRIMARY
        )
        self.control_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.control_frame.columnconfigure(1, weight=1)

        # --- File Selection Row ---
        self.filename_label = ttk.Label(
            self.control_frame,
            text="Output File:",
            anchor="w"
        )
        self.filename_label.grid(row=0, column=0, padx=(0, 10), pady=(5, 10), sticky="w")

        self.filename_var = tk.StringVar(value=DEFAULT_OUTPUT_FILENAME)
        self.filename_entry = ttk.Entry(
            self.control_frame,
            textvariable=self.filename_var,
            width=50
        )
        self.filename_entry.grid(row=0, column=1, padx=5, pady=(5, 10), sticky="ew")

        self.browse_button = ttk.Button(
            self.control_frame,
            text="Browse...",
            command=self.browse_file,
            bootstyle="info-outline"
        )
        self.browse_button.grid(row=0, column=2, padx=(5, 0), pady=(5, 10), sticky="e")


        # --- City Selection Row ---
        self.city_label = ttk.Label(
            self.control_frame,
            text="Select City:",
            anchor="w"
        )
        self.city_label.grid(row=1, column=0, padx=(0, 10), pady=(5, 10), sticky="w")

        self.config_cities = CITIES if isinstance(CITIES, list) else []
        self.city_options = ["All Cities"] + self.config_cities
        self.selected_city_var = tk.StringVar()

        self.city_combobox = ttk.Combobox(
            self.control_frame,
            textvariable=self.selected_city_var,
            values=self.city_options,
            state='readonly',
            bootstyle=PRIMARY
        )
        if self.city_options:
            self.city_combobox.current(0)
        else:
            self.city_combobox.config(state='disabled')
            self.selected_city_var.set("No cities configured!")
        self.city_combobox.grid(row=1, column=1, columnspan=2, padx=5, pady=(5, 10), sticky="ew")


        # --- Action Row ---
        self.action_frame = ttk.Frame(self.control_frame)
        self.action_frame.grid(row=2, column=0, columnspan=3, pady=(15, 5), sticky="ew")
        self.action_frame.columnconfigure(0, weight=1)

        self.start_button = ttk.Button(
            self.action_frame,
            text="Start Scraping",
            command=self.start_scraping_thread,
            bootstyle="success",
            width=20
        )
        self.start_button.pack(pady=5)


        # --- Log Area ---
        self.log_frame = ttk.LabelFrame(
            self.main_frame,
            text=" Logs ",
            padding=10,
            bootstyle=PRIMARY
        )
        self.log_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10)) # Adjusted row index
        self.log_frame.rowconfigure(0, weight=1)
        self.log_frame.columnconfigure(0, weight=1)

        # Get initial theme colors for ScrolledText background/foreground
        initial_bg = self.style.colors.get('bg')
        initial_fg = self.style.colors.get('fg')


        self.log_text = ScrolledText(
            self.log_frame,
            padding=5,
            height=15,
            autohide=True,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.text.config(background=initial_bg, foreground=initial_fg)

        self.configure_log_tags()
        # --- Status Bar ---
        self.status_frame = ttk.Frame(self.main_frame, padding=(5, 5))
        self.status_frame.grid(row=4, column=0, sticky="ew") # Adjusted row index
        self.status_frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready. Select city and output file.")
        self.status_label = ttk.Label(
            self.status_frame,
            textvariable=self.status_var,
            bootstyle="secondary",
            anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

        # Progress bar (hidden initially)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.status_frame,
            variable=self.progress_var,
            mode='indeterminate',
            bootstyle="success-striped"
        )
        # Will be gridded in when needed

        # --- Initialize variables ---
        self.scraping_active = False
        self.all_data = []
        self.scrape_thread = None


    # ADD THIS HELPER METHOD
    def _load_theme_preference(self):
        """Loads the theme name from the settings file, returns default if not found/invalid."""
        default = DEFAULT_DARK_THEME
        try:
            if os.path.exists(THEME_SETTINGS_FILE):
                with open(THEME_SETTINGS_FILE, 'r') as f:
                    theme_name = f.read().strip()
                # Validate if it's one of our known themes
                if theme_name in [DEFAULT_DARK_THEME, DEFAULT_LIGHT_THEME]:
                    print(f"INFO: Loaded theme preference: {theme_name}")
                    return theme_name
                else:
                    print(f"WARN: Invalid theme '{theme_name}' found in {THEME_SETTINGS_FILE}. Using default.")
            else:
                 # Optional: Log if file doesn't exist on first run
                 # print(f"INFO: Theme settings file '{THEME_SETTINGS_FILE}' not found. Using default.")
                 pass # Silently use default if no file
        except Exception as e:
            print(f"WARN: Error reading theme settings file '{THEME_SETTINGS_FILE}': {e}. Using default.")
        return default

    # ADD THIS HELPER METHOD
    def _save_theme_preference(self, theme_name):
        """Saves the given theme name to the settings file."""
        try:
            with open(THEME_SETTINGS_FILE, 'w') as f:
                f.write(theme_name)
            # Optional: Log success
            # print(f"INFO: Saved theme preference: {theme_name}")
        except Exception as e:
            # Use update_log if available and safe, otherwise print
            log_func = getattr(self, 'update_log', print)
            try:
                log_func(f"WARN: Could not save theme setting to '{THEME_SETTINGS_FILE}': {e}", "WARNING")
            except: # Fallback if update_log fails (e.g., during shutdown)
                print(f"WARN: Could not save theme setting to '{THEME_SETTINGS_FILE}': {e}")

    def configure_log_tags(self):
        """Configures the tags used for styling text in the log area."""
        colors = self.style.colors
        base_font_family = "Helvetica"
        base_font_size = 10

        self.log_text.tag_configure('INFO', foreground=colors.get('fg'))
        self.log_text.tag_configure('WARNING', foreground=colors.warning)
        self.log_text.tag_configure('ERROR', foreground=colors.danger, font=(base_font_family, base_font_size, "bold"))
        self.log_text.tag_configure('SUCCESS', foreground=colors.success)
        self.log_text.tag_configure('CITY_HEADER', foreground=colors.info, font=(base_font_family, base_font_size, "bold"))
        self.log_text.tag_configure('CAPTCHA', foreground=colors.primary, font=(base_font_family, base_font_size, "bold"))


    def toggle_theme(self):
        """Switches between the light and dark themes."""
        if self.dark_mode_var.get(): # If var is now True, user wants DARK mode
            new_theme = DEFAULT_DARK_THEME
            toggle_text = "🌙"
        else: # If var is now False, user wants LIGHT mode
            new_theme = DEFAULT_LIGHT_THEME
            toggle_text = "☀️"

        try:
            current_theme = self.style.theme.name
            if current_theme != new_theme:
                self.style.theme_use(new_theme)
                self.update_log(f"Theme changed to: {new_theme}", "INFO")

                # --- ADD THIS: Save the newly selected theme ---
                self._save_theme_preference(new_theme)
                # ------------------------------------------------

                self.theme_toggle.config(text=toggle_text) # Update toggle text

                # --- Update widget styles that don't auto-update ---
                new_bg = self.style.colors.get('bg')
                new_fg = self.style.colors.get('fg')
                self.log_text.text.config(background=new_bg, foreground=new_fg)
                self.configure_log_tags() # Reconfigure tags for new colors

            else:
                # Theme is already the one selected, ensure toggle text is still correct
                self.theme_toggle.config(text=toggle_text)

        except tk.TclError as e:
            self.update_log(f"Error changing theme: {e}", "ERROR")
            # Attempt to revert the variable state if theme change failed (optional)
            # self.dark_mode_var.set(not self.dark_mode_var.get())


    def browse_file(self):
        """Opens a file dialog to select the save location and filename."""
        current_path = self.filename_var.get()
        initial_dir = os.path.dirname(current_path) if os.path.dirname(current_path) and os.path.isdir(os.path.dirname(current_path)) else os.getcwd()
        initial_file = os.path.basename(current_path) if current_path else DEFAULT_OUTPUT_FILENAME

        filetypes = [("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]

        filepath = filedialog.asksaveasfilename(
            title="Save Scraped Data As",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".xlsx",
            filetypes=filetypes,
            parent=self.root
        )

        if filepath:
            # Simple check to add default extension if user removed it but selected type
            root_ext, ext = os.path.splitext(filepath)
            if not ext:
                selected_type = next((ft[1] for ft in filetypes if ft[0] == "Excel files"), ".xlsx") # Default to excel ext
                # Basic logic, might need refinement based on exact filedialog behavior
                if filepath.lower().endswith(('.xlsx', '.csv')):
                    pass # Already has an extension
                elif ".xlsx" in selected_type:
                     filepath += ".xlsx"
                elif ".csv" in selected_type:
                     filepath += ".csv"
                else: # All files or unknown
                     filepath += ".xlsx" # Fallback default

            self.filename_var.set(filepath)
            self.update_log(f"Output file set to: {filepath}", "INFO")

    # ... (rest of the update_log, update_status, start_scraping_thread methods remain the same) ...
    def update_log(self, message, level="INFO"):
        """Safely appends a message to the log area from any thread with optional level tagging."""
        def _append():
            if not self.root or not self.root.winfo_exists() or not hasattr(self, 'log_text') or not self.log_text.winfo_exists():
                 print(f"Log Error: GUI element destroyed. Msg: {message}")
                 return

            try:
                tag = level.upper() if level.upper() in ['INFO', 'WARNING', 'ERROR', 'SUCCESS', 'CITY_HEADER', 'CAPTCHA'] else 'INFO'

                # Handle specific message keywords for tags if level is generic
                if tag == 'INFO': # Only check keywords if level is INFO
                     msg_upper = message.upper()
                     if "=== BẮT ĐẦU" in message or "=== HOÀN THÀNH" in message or "===" in message: tag = 'CITY_HEADER'
                     elif "ĐÃ LƯU XONG" in message or "✅" in message or "SAVED" in msg_upper: tag = 'SUCCESS'
                     elif "CAPTCHA" in msg_upper: tag = 'CAPTCHA'
                     elif "WARN" in msg_upper or "CẢNH BÁO" in msg_upper: tag = 'WARNING'
                     elif "ERROR" in msg_upper or "LỖI" in msg_upper or "FAIL" in msg_upper: tag = 'ERROR'


                # Ensure the tag exists before using it (safety check)
                if tag not in self.log_text.tag_names():
                    # Try to reconfigure tags if one is missing (might happen if theme changed)
                    try: self.configure_log_tags()
                    except: pass # Ignore errors during this recovery attempt

                    if tag not in self.log_text.tag_names():
                         print(f"Log Warning: Tag '{tag}' not configured. Using 'INFO'.")
                         tag = 'INFO'


                self.log_text.insert(tk.END, message + '\n', (tag,))
                self.log_text.see(tk.END) # Scroll to the end
            except tk.TclError as e:
                 # Ignore errors likely related to widget destruction during close
                 if "invalid command name" not in str(e).lower():
                      print(f"Log Error (TclError): {e}. Msg: {message}")
            except Exception as e:
                 print(f"Log Error (Exception): {e}. Msg: {message}")
                 traceback.print_exc()

        # Schedule the update on the main thread safely
        if hasattr(self.root, 'after'):
            try:
                 self.root.after(0, _append)
            except tk.TclError: # Handle case where root window is destroyed
                 print(f"Log Error: Window destroyed before scheduling. Msg: {message}")


    def update_status(self, message):
        """Safely updates the status bar from any thread."""
        def _update():
            if not self.root or not self.root.winfo_exists() or not hasattr(self, 'status_var'):
                print(f"Status Error: GUI element destroyed. Msg: {message}")
                return
            try:
                self.status_var.set(message)
            except tk.TclError as e:
                 if "invalid command name" not in str(e).lower():
                      print(f"Status Error (TclError): {e}. Msg: {message}")
            except Exception as e:
                 print(f"Status Error (Exception): {e}. Msg: {message}")

        # Schedule the update on the main thread
        if hasattr(self.root, 'after'):
            try:
                 self.root.after(0, _update)
            except tk.TclError:
                 print(f"Status Error: Window destroyed before scheduling. Msg: {message}")

    def start_scraping_thread(self):
        """Starts the scraping process in a new thread."""
        if self.scraping_active:
            Messagebox.show_warning(
                "Scraping is already in progress.",
                "Busy",
                parent=self.root
            )
            return

        output_file = self.filename_var.get().strip()
        selected_city_option = self.selected_city_var.get().strip()

        # --- Input Validations ---
        if not output_file:
            Messagebox.show_error("Please specify an output filename.", "Error", parent=self.root)
            return

        if not selected_city_option or selected_city_option == "No cities configured!":
            Messagebox.show_error("Please select a city.", "Error", parent=self.root)
            return

        # --- Directory and Permissions Validation ---
        output_dir = os.path.dirname(output_file)
        if not output_dir: # If only a filename is given, use current directory
            output_dir = os.getcwd()
            # Update the full path in the entry box
            output_file = os.path.join(output_dir, output_file)
            self.filename_var.set(output_file)

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.update_log(f"Created output directory: {output_dir}", level="INFO")
            except OSError as e:
                Messagebox.show_error(
                    f"Could not create directory:\n{output_dir}\nError: {e}",
                    "Directory Error", parent=self.root
                )
                self.update_log(f"Directory creation failed: {e}", level="ERROR")
                return

        if not os.access(output_dir, os.W_OK):
            Messagebox.show_error(
                f"Cannot write to directory:\n{output_dir}\nCheck permissions.",
                "Permission Error", parent=self.root
            )
            self.update_log(f"Write permission denied for directory: {output_dir}", level="ERROR")
            return

        # --- File Extension Validation ---
        allowed_extensions = [".xlsx", ".csv"]
        file_ext = os.path.splitext(output_file)[1].lower()
        if file_ext not in allowed_extensions:
             confirmed = Messagebox.askyesno(
                 title="Filename Warning",
                 question=f"Filename '{os.path.basename(output_file)}' doesn't end with .xlsx or .csv.\nSaving might default to CSV or fail.\n\nContinue anyway?",
                 parent=self.root
             )
             if not confirmed:
                 self.update_status("Save cancelled due to file extension warning.")
                 return

        # --- Start Scraping ---
        self.scraping_active = True
        self.toggle_controls(enabled=False)

        self.progress_bar.grid(row=0, column=1, padx=(10, 0), sticky="e")
        self.progress_bar.start(10)

        self.update_status(f"Starting scraper for: '{selected_city_option}'...")
        self.log_text.delete('1.0', tk.END) # Clear log on new run
        self.all_data = [] # Clear previous data

        self.scrape_thread = threading.Thread(
            target=self.run_scraping_task,
            args=(selected_city_option,),
            daemon=True # Ensure thread exits if main app closes unexpectedly
        )
        self.scrape_thread.start()


    def toggle_controls(self, enabled=True):
        """Enable or disable input controls."""
        state = tk.NORMAL if enabled else tk.DISABLED
        # Use 'readonly' for entry/combobox when enabled, 'disabled' otherwise
        readonly_state = 'readonly' if enabled else tk.DISABLED

        # Wrap in try-except for safety during theme changes or shutdown
        try:
            if self.start_button.winfo_exists():
                self.start_button.config(state=state)
        except tk.TclError: pass
        try:
            if self.browse_button.winfo_exists():
                self.browse_button.config(state=state)
        except tk.TclError: pass
        try:
            if self.filename_entry.winfo_exists():
                # Filename entry should be editable when enabled
                self.filename_entry.config(state=tk.NORMAL if enabled else tk.DISABLED)
        except tk.TclError: pass
        try:
            if self.city_combobox.winfo_exists():
                 current_city_text = self.selected_city_var.get()
                 combobox_state = readonly_state if enabled and current_city_text != "No cities configured!" else tk.DISABLED
                 self.city_combobox.config(state=combobox_state)
        except tk.TclError: pass
        # Also toggle the theme button state
        try:
            if self.theme_toggle.winfo_exists():
                self.theme_toggle.config(state=state)
        except tk.TclError: pass

    def run_scraping_task(self, selected_city_option):
        """The function executed by the worker thread."""
        start_time = time.time()
        self.update_log(f"=== BẮT ĐẦU SCRAPE CHO: '{selected_city_option}' ===", level="CITY_HEADER")

        total_results_overall = 0
        cities_processed = 0
        cities_with_errors = 0
        cities_with_captcha_block = 0

        try:
            all_config_cities = self.config_cities # Get list from class attribute

            if selected_city_option == "All Cities":
                if not all_config_cities:
                    self.update_log("ERROR: 'All Cities' selected, but CITIES list in config.py is empty.", level="ERROR")
                    self.root.after(0, self.on_scraping_complete, 0, 0, 0, 0) # Schedule completion call
                    return
                cities_to_scrape = all_config_cities
                log_msg = f"--- Mode: Scraping ALL {len(cities_to_scrape)} cities from config ---"
            else:
                cities_to_scrape = [selected_city_option]
                log_msg = f"--- Mode: Scraping selected city: {selected_city_option} ---"

            self.update_log(log_msg, level="INFO")
            num_cities = len(cities_to_scrape)

            if num_cities == 0:
                self.update_log("No cities to scrape.", level="WARNING")
                self.root.after(0, self.on_scraping_complete, 0, 0, 0, 0)
                return

            for city_index, city in enumerate(cities_to_scrape):
                # Simple check if scraping was aborted externally (less reliable than explicit stop event)
                if not self.scraping_active:
                     self.update_log(f"Scraping aborted before processing {city}.", "WARNING")
                     break # Exit loop if flag turned false

                city_start_time = time.time()
                status_msg = f"Scraping city {city_index + 1}/{num_cities}: {city}..."
                self.update_status(status_msg)
                self.update_log(f"\n--- Starting city: {city} ({city_index + 1}/{num_cities}) ---", level="INFO")

                city_data_list = []
                city_status = "UNKNOWN"

                try:
                    # Ensure scraper function exists before calling
                    if 'scrape_city' in globals() and callable(scrape_city):
                        city_data_list, city_status = scrape_city(city, self.update_log)
                    else:
                        # Log error specifically if the function is missing
                        self.update_log(f"[{city}] ERROR: Scraper function 'scrape_city' is not available.", "ERROR")
                        city_status = "ERROR"
                        city_data_list = [] # Ensure list is empty

                    # Process results based on status
                    if city_status == "OK":
                        if city_data_list: # Check if list has data
                            self.all_data.extend(city_data_list)
                            count = len(city_data_list)
                            total_results_overall += count
                            self.update_log(f"[{city}] ✅ Success: Found {count} results. Total collected: {total_results_overall}.", level="SUCCESS")
                        else:
                            self.update_log(f"[{city}] ℹ️ Completed: No results found for this city.", level="INFO")
                            # Keep status as OK or maybe change to NO_RESULTS if needed downstream
                            city_status = "NO_RESULTS" # Explicitly mark no results found

                    elif city_status == "CAPTCHA_EARLY":
                        self.update_log(f"[{city}] ⚠️ Blocked by CAPTCHA at search level. Skipping city.", level="CAPTCHA")
                        cities_with_captcha_block += 1
                    elif city_status == "NO_RESULTS": # Handle explicit NO_RESULTS from scraper
                         self.update_log(f"[{city}] ℹ️ Scraper reported no results found.", level="INFO")
                    elif city_status == "ERROR":
                         # Avoid double logging if already logged about missing function
                        log_content = self.log_text.get("1.0", tk.END) # Get current log text
                        missing_func_msg = f"ERROR: Scraper function 'scrape_city' is not available."
                        if missing_func_msg not in log_content:
                             self.update_log(f"[{city}] ❌ Scraper reported an ERROR. Check logs above.", level="ERROR")
                        cities_with_errors += 1
                    else: # Handle unexpected status codes
                        self.update_log(f"[{city}] ❓ Unknown status from scraper: '{city_status}'. Treating as error.", level="WARNING")
                        cities_with_errors += 1

                except Exception as e_city_run:
                    # Catch exceptions directly from the scrape_city call itself
                    self.update_log(f"!!! CRITICAL ERROR while running scrape_city for {city} !!!", level="ERROR")
                    self.update_log(traceback.format_exc(), level="ERROR")
                    cities_with_errors += 1
                    city_status = "CRITICAL_ERROR" # Mark status
                finally:
                    cities_processed += 1
                    city_end_time = time.time()
                    self.update_log(f"=== Finished {city} in {city_end_time - city_start_time:.2f}s (Status: {city_status}) ===", level="CITY_HEADER")

                # Pause between cities if scraping multiple
                if num_cities > 1 and city_index < num_cities - 1 and self.scraping_active:
                    pause_duration = random.uniform(3.0, 7.0) # Random pause between 3-7 seconds
                    self.update_status(f"Pausing for {pause_duration:.1f}s before next city...")
                    self.update_log(f"--- Pausing for {pause_duration:.1f} seconds ---", level="INFO")
                    time.sleep(pause_duration)

            # Check if loop finished or was aborted
            if not self.scraping_active:
                 self.update_log("--- Scraping aborted by user or error ---", "WARNING")
                 # Optionally, decide if partially collected data should be saved or discarded
                 # For simplicity, we'll proceed to save whatever was collected before abortion

            # Schedule completion task on main GUI thread
            self.root.after(0, self.on_scraping_complete, cities_processed, cities_with_errors, cities_with_captcha_block, total_results_overall)

        except Exception as e_thread:
            # Catch errors in the thread's main loop structure (outside city loop)
            self.update_log(f"!!! CRITICAL ERROR IN MAIN SCRAPING THREAD !!!", level="ERROR")
            self.update_log(traceback.format_exc(), level="ERROR")
            # Schedule error handling on main GUI thread
            self.root.after(0, self.on_scraping_error, f"Critical error in thread loop: {e_thread}")

        finally:
            # This block always runs when the thread function finishes (normally or via exception)
            end_time = time.time()
            total_duration = end_time - start_time
            self.update_log(f"\n=== SCRAPING THREAD FINISHED IN {total_duration:.2f} seconds ({total_duration/60:.2f} minutes) ===", level="INFO")


    def on_scraping_complete(self, cities_processed, cities_with_errors, cities_with_captcha_block, total_results_found):
        """Tasks to run in the main thread after scraping loop finishes."""
        try:
            if self.progress_bar.winfo_exists():
                self.progress_bar.stop()
                self.progress_bar.grid_forget()
        except tk.TclError: pass # Ignore if widget destroyed

        self.update_status("Scraping finished. Processing and saving results...")
        self.update_log("\n--- Processing and Saving Results ---", level="CITY_HEADER")

        output_file = self.filename_var.get()
        export_successful = False
        final_save_path = output_file
        saved_format = ""
        actual_saved_count = 0 # Track rows actually saved

        if self.all_data: # Check if any data was collected
            final_count = len(self.all_data)
            self.update_log(f"Total items collected: {final_count}. Preparing to save...", level="INFO")

            try:
                # Create DataFrame
                df = pd.DataFrame(self.all_data)
                self.update_log("Structuring DataFrame...", level="INFO")

                # Define desired column order and ensure all exist
                columns_order = [
                    "Thành phố", "Tên công ty", "Địa chỉ", "Số điện thoại", "Website",
                    "Giờ hoạt động", "Google Maps URL", "Vĩ độ", "Kinh độ", "Notes"
                ]
                for col in columns_order:
                    if col not in df.columns:
                        df[col] = pd.NA # Add missing columns with NA placeholder

                # Reindex to enforce order
                df = df.reindex(columns=columns_order)

                self.update_log("Cleaning data (filling N/A, stripping whitespace)...", level="INFO")

                # Define common placeholders for missing/error data
                error_placeholders = [
                    '', None, pd.NA, 'Lỗi xử lý', 'Chưa lấy', 'Không tìm thấy', 'Lỗi',
                    'Không lấy được địa chỉ', 'Thất bại', 'Lỗi tải trang (Timeout)', 'Lỗi tải trang',
                    'Không lấy được SĐT', 'Không tìm thấy địa chỉ',
                    'Không tìm thấy SĐT', 'Lỗi phân tích URL', 'URL không hợp lệ', 'Không có trang web',
                    'Chưa thử lấy giờ', 'Không tìm thấy thông tin giờ', 'Lỗi Stale lấy text giờ',
                    'Lỗi xử lý giờ (ngoài)', 'Lỗi tọa độ', 'Lỗi xử lý kết quả', 'CAPTCHA Blocked',
                    # Add any other specific error strings your scraper might produce
                ]
                # Create a dictionary for replacement: {placeholder: 'N/A'}
                replace_dict = {placeholder: 'N/A' for placeholder in error_placeholders}

                # Identify string columns to clean (excluding Notes and Giờ hoạt động which need special handling)
                string_cols_to_clean = df.select_dtypes(include=['object']).columns.difference(['Notes', 'Giờ hoạt động'])

                # Clean string columns
                for col in string_cols_to_clean:
                    if col in df.columns: # Check if column exists from reindex
                        df[col] = df[col].fillna('N/A') # Fill Pandas NA/None first
                        df[col] = df[col].replace(replace_dict) # Replace known error strings
                        df[col] = df[col].astype(str).str.strip() # Convert to string and strip whitespace
                        df.loc[df[col] == '', col] = 'N/A' # Replace empty strings after stripping

                # Special handling for 'Giờ hoạt động' (preserve newlines but clean errors/whitespace)
                if "Giờ hoạt động" in df.columns:
                     df["Giờ hoạt động"] = df["Giờ hoạt động"].fillna('N/A')
                     df["Giờ hoạt động"] = df["Giờ hoạt động"].replace(replace_dict)
                     df["Giờ hoạt động"] = df["Giờ hoạt động"].astype(str).str.strip() # Strip leading/trailing whitespace
                     # Replace multiple newlines with a single one
                     df["Giờ hoạt động"] = df["Giờ hoạt động"].str.replace(r'\n\s*\n', '\n', regex=True)
                     # Standardize common 'not found' variations after cleaning
                     df.loc[df["Giờ hoạt động"].str.upper().isin(['', 'N/A', 'KHÔNG TÌM THẤY THÔNG TIN GIỜ']), "Giờ hoạt động"] = 'N/A'

                # Ensure 'Notes' column exists and fill NAs with empty string
                if "Notes" in df.columns:
                    df["Notes"] = df["Notes"].fillna("")
                else:
                    df["Notes"] = "" # Add Notes column if missing

                # --- Ready to Save ---
                df_to_save = df
                actual_saved_count = len(df_to_save) # Get count before saving
                self.update_log(f"Data cleaning finished. Attempting to save {actual_saved_count} rows.", level="INFO")

                save_attempted = False
                file_ext = os.path.splitext(output_file)[1].lower()

                # Ensure directory exists right before saving (double-check)
                output_dir = os.path.dirname(output_file)
                if output_dir and not os.path.exists(output_dir):
                    try:
                        os.makedirs(output_dir)
                        self.update_log(f"Ensured output directory exists: {output_dir}", "INFO")
                    except OSError as e:
                        self.update_log(f"ERROR: Could not create directory before saving: {e}", "ERROR")
                        Messagebox.showerror("Save Error", f"Could not create directory:\n{output_dir}\nSaving failed.", parent=self.root)
                        df_to_save = None # Prevent save attempt if directory creation failed

                if df_to_save is not None: # Proceed only if directory is okay and df exists
                    if file_ext == ".xlsx":
                        try:
                            save_attempted = True
                            # Make sure openpyxl is installed: pip install openpyxl
                            df_to_save.to_excel(output_file, index=False, engine='openpyxl')
                            self.update_log(f"\n✅ Successfully saved data to Excel: '{output_file}'", level="SUCCESS")
                            export_successful = True
                            final_save_path = output_file
                            saved_format = "Excel"
                        except ImportError:
                            self.update_log("\n❌ ERROR: 'openpyxl' library not found. Please install it: pip install openpyxl", level="ERROR")
                            Messagebox.show_error(
                                "Missing Library",
                                "'openpyxl' is required to save Excel (.xlsx) files.\nInstall it using: pip install openpyxl\n\nAlternatively, save as a .csv file.",
                                parent=self.root
                            )
                        except Exception as e_excel:
                            self.update_log(f"\n❌ ERROR saving Excel file '{output_file}': {e_excel}", level="ERROR")
                            self.update_log(traceback.format_exc(), level="ERROR")
                            Messagebox.show_error(f"Failed to save Excel file:\n{e_excel}", "Excel Export Error", parent=self.root)

                    elif file_ext == ".csv":
                        try:
                            save_attempted = True
                            # Use utf-8-sig for better Excel compatibility with UTF-8 chars
                            df_to_save.to_csv(output_file, index=False, encoding='utf-8-sig')
                            self.update_log(f"\n✅ Successfully saved data to CSV: '{output_file}'", level="SUCCESS")
                            export_successful = True
                            final_save_path = output_file
                            saved_format = "CSV"
                        except Exception as e_csv:
                            self.update_log(f"\n❌ ERROR saving CSV file '{output_file}': {e_csv}", level="ERROR")
                            self.update_log(traceback.format_exc(), level="ERROR")
                            Messagebox.show_error(f"Failed to save CSV file:\n{e_csv}", "CSV Export Error", parent=self.root)

                    else: # Fallback for unknown/missing extensions -> Save as CSV
                        self.update_log(f"\n⚠️ Unsupported or missing file extension '{file_ext}'. Attempting to save as CSV instead.", level="WARNING")
                        # Create a fallback path with .csv extension
                        fallback_csv_path = os.path.splitext(output_file)[0] + ".csv"
                        # Ensure fallback directory exists too
                        fallback_dir = os.path.dirname(fallback_csv_path)
                        if fallback_dir and not os.path.exists(fallback_dir):
                             try: os.makedirs(fallback_dir)
                             except OSError: pass # Ignore error here, let to_csv handle final check

                        try:
                            save_attempted = True
                            df_to_save.to_csv(fallback_csv_path, index=False, encoding='utf-8-sig')
                            self.update_log(f"   ✅ Data saved to fallback CSV: '{fallback_csv_path}'", level="SUCCESS")
                            export_successful = True
                            final_save_path = fallback_csv_path # Update path to where it was actually saved
                            saved_format = "CSV (Fallback)"
                            # Inform user about the fallback save
                            Messagebox.show_warning(
                                "Saved as CSV",
                                f"Unrecognized file extension '{file_ext}'.\nData has been saved as CSV:\n'{os.path.basename(fallback_csv_path)}'",
                                parent=self.root)
                        except Exception as e_csv_fallback:
                            self.update_log(f"   ❌ ERROR saving fallback CSV file: {e_csv_fallback}", level="ERROR")
                            self.update_log(traceback.format_exc(), level="ERROR")
                            Messagebox.showerror("Fallback Save Error", f"Failed to save fallback CSV file:\n{e_csv_fallback}", parent=self.root)

                    # Log if saving wasn't even attempted but data was present
                    if not save_attempted and df_to_save is not None:
                        self.update_log("\n⚠️ File saving was not attempted (likely due to directory error).", level="WARNING")

            except Exception as e_df:
                 # Catch broad errors during DataFrame creation or processing
                 self.update_log(f"\n❌ CRITICAL ERROR during data processing/cleaning: {e_df}", level="ERROR")
                 self.update_log(traceback.format_exc(), level="ERROR")
                 Messagebox.showerror("Data Processing Error", f"An error occurred while processing the collected data:\n{e_df}", parent=self.root)
                 export_successful = False # Mark export as failed

        else:
            # Case where self.all_data was empty after scraping
            self.update_log("\n🤷 No data was collected during the scrape.", level="WARNING")
            # Show info message unless errors occurred during scraping
            if cities_with_errors == 0 and cities_with_captcha_block == 0:
                 Messagebox.showinfo("No Data", "The scraping process completed, but no data was collected or available to save.", parent=self.root)
            export_successful = True # Consider completion without data as 'successful' in terms of flow


        # --- Finalize GUI State ---
        final_summary_msg = f"Completed. Processed {cities_processed} cities."
        if export_successful :
             if self.all_data and saved_format and actual_saved_count > 0: # Check if data existed and was saved
                  final_summary_msg += f" Saved {actual_saved_count} rows to {os.path.basename(final_save_path)} ({saved_format})."
             elif not self.all_data: # No data collected case
                  final_summary_msg += " No data collected."
             elif self.all_data and not saved_format: # Data existed but save failed
                  final_summary_msg += f" Failed to save {len(self.all_data)} results. Check logs."
        else: # Export explicitly failed (e.g., processing error, save error)
             final_summary_msg = f"Completed with errors. Processed {cities_processed} cities. Failed to save results."

        # Add notes about errors/captcha blocks
        status_notes = []
        if cities_with_captcha_block > 0: status_notes.append(f"{cities_with_captcha_block} cities CAPTCHA blocked")
        if cities_with_errors > 0: status_notes.append(f"{cities_with_errors} cities had errors")
        if status_notes: final_summary_msg += f" ({'; '.join(status_notes)})."

        self.update_status(final_summary_msg)

        # --- Cleanup ---
        self.scraping_active = False
        self.toggle_controls(enabled=True) # Re-enable controls


    def on_scraping_error(self, error_message):
        """Tasks to run in the main thread if a critical error occurred in the thread loop."""
        try:
            if self.progress_bar.winfo_exists():
                self.progress_bar.stop()
                self.progress_bar.grid_forget()
        except tk.TclError: pass

        self.update_log(f"\n--- SCRAPING HALTED DUE TO CRITICAL ERROR ---", level="ERROR")
        self.update_status(f"Critical Error: Scraping stopped. Check logs.")
        Messagebox.showerror("Scraping Error", f"A critical error stopped the process:\n{error_message}\n\nPlease check the logs for details.", parent=self.root)

        # --- Cleanup on Error ---
        self.scraping_active = False
        self.toggle_controls(enabled=True) # Re-enable controls even on error


# --- Main Execution ---
if __name__ == "__main__":
    # Load initial theme preference *before* creating the Window
    # This way, the window itself respects the theme from the start
    initial_theme = DEFAULT_DARK_THEME # Default assumption
    try:
        if os.path.exists(THEME_SETTINGS_FILE):
            with open(THEME_SETTINGS_FILE, 'r') as f:
                theme_name = f.read().strip()
            if theme_name in [DEFAULT_DARK_THEME, DEFAULT_LIGHT_THEME]:
                initial_theme = theme_name
    except Exception as e:
        print(f"WARN: Could not preload theme setting: {e}")

    # Use ttkbootstrap Window with the determined initial theme
    root = ttk.Window(themename=initial_theme)

    app = ScraperApp(root)

    # Graceful shutdown handling
    def on_closing():
        if app.scraping_active:
            if Messagebox.askyesno("Quit", "Scraping is active. Quit anyway?\n(This may corrupt the save file if currently writing)", parent=root):
                print("Attempting abrupt shutdown...")
                # Set flag to potentially stop thread loop (if checked)
                app.scraping_active = False
                # Optional: Give thread a moment to notice? Unreliable.
                # time.sleep(0.5)
                root.destroy() # Destroy window, daemon thread should exit
            else:
                return # Don't close if user cancels
        else:
             print("Closing application.")
             # Optional: Save final theme state on clean exit?
             # current_theme_name = app.style.theme.name
             # app._save_theme_preference(current_theme_name)
             root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()