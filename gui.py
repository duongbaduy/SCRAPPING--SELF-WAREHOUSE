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
import re # Import regex for sanitization
from collections import OrderedDict # To keep region order

# --- Project Imports ---
# Ensure config.py exists and has the variables
try:
    # Import the new structure
    from config import REGIONS_AND_CITIES, DEFAULT_OUTPUT_FILENAME, THEME_SETTINGS_FILE
    # Ensure REGIONS_AND_CITIES is a dict, provide empty dict fallback
    if not isinstance(REGIONS_AND_CITIES, dict):
        print("WARN: REGIONS_AND_CITIES in config.py is not a dictionary. Using empty dataset.")
        REGIONS_AND_CITIES = {}
except ImportError:
    print("WARN: config.py not found or missing definitions. Using defaults.")
    REGIONS_AND_CITIES = {"Example Region": ["Example City 1", "Example City 2"]} # Provide minimal example structure
    DEFAULT_OUTPUT_FILENAME = "gmaps_data_fallback.xlsx"
    THEME_SETTINGS_FILE = "theme_setting.txt" # Ensure this is defined

# Ensure scraper.py exists and has the function
try:
    from scraper import scrape_city
except ImportError:
    print("ERROR: scraper.py or the scrape_city function not found. GUI will load but scraping will fail.")
    # Define a dummy function for GUI testing if scraper is missing
    def scrape_city(city, logger_callback):
        logger_callback(f"ERROR: Scraper function 'scrape_city' not found for {city}.", "ERROR")
        # Simulate some work and return empty data
        time.sleep(0.5)
        return [], "ERROR"

# --- Default Theme Options ---
DEFAULT_DARK_THEME = 'darkly'
DEFAULT_LIGHT_THEME = 'cosmo' # Or choose another like 'litera', 'lumen', 'flatly'

# --- Settings File ---
# Ensure this is defined (even if imported from config, define fallback here)
if 'THEME_SETTINGS_FILE' not in globals():
     THEME_SETTINGS_FILE = "theme_setting.txt"

# --- Filename Sanitization ---
def _sanitize_filename_part(part):
    """Removes or replaces characters unsafe for filenames."""
    if not part:
        return ""
    # Remove leading/trailing whitespace
    part = part.strip()
    # Replace spaces and common separators with underscore
    part = re.sub(r'[\s/\\:]+', '_', part)
    # Remove characters not allowed in most file systems
    part = re.sub(r'[<>:"|?*]+', '', part)
    # Limit length (optional, but good practice)
    part = part[:50] # Limit each part to 50 chars
    return part

# --- GUI Application Class ---
class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Maps Scraper - Self Storage Australia")

        # --- START: Center the Window ---
        window_width = 800
        window_height = 800 # Increased height slightly for region selector

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        center_x = int((screen_width / 2) - (window_width / 2))
        center_y = int((screen_height / 2) - (window_height / 2))

        self.root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
        # --- END: Center the Window ---

        self.root.minsize(700, 650) # Adjusted min height

        # --- Theme Loading ---
        saved_theme = self._load_theme_preference()
        is_dark_initially = (saved_theme == DEFAULT_DARK_THEME)

        self.dark_mode_var = BooleanVar(value=is_dark_initially)
        self.style = ttk.Style(theme=saved_theme)

        # --- Load Region/City Data ---
        # Use OrderedDict to maintain config file order in dropdown
        self.regions_data = OrderedDict(REGIONS_AND_CITIES)

        # --- Store Initial Filename Parts ---
        self.initial_output_dir = os.path.dirname(DEFAULT_OUTPUT_FILENAME) or os.getcwd()
        self.initial_output_base = os.path.splitext(os.path.basename(DEFAULT_OUTPUT_FILENAME))[0]
        self.initial_output_ext = os.path.splitext(DEFAULT_OUTPUT_FILENAME)[1] or ".xlsx"

        # --- Main Frame ---
        self.main_frame = ttk.Frame(self.root, padding=20)
        self.main_frame.pack(fill=BOTH, expand=YES)

        # Configure row/column weights for responsiveness
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(4, weight=1) # Log area row index changed

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
        initial_toggle_text = "🌙" if is_dark_initially else "☀️"
        self.theme_toggle = ttk.Checkbutton(
            self.header_frame,
            text=initial_toggle_text,
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
        self.control_frame.columnconfigure(1, weight=1) # Allow entry/combos to expand

        # --- File Selection Row ---
        self.filename_label = ttk.Label(self.control_frame, text="Output File:", anchor="w")
        self.filename_label.grid(row=0, column=0, padx=(0, 10), pady=(5, 10), sticky="w")

        # Use initial default filename
        self.filename_var = tk.StringVar(value=os.path.join(self.initial_output_dir, self.initial_output_base + self.initial_output_ext))
        self.filename_entry = ttk.Entry(self.control_frame, textvariable=self.filename_var, width=50)
        self.filename_entry.grid(row=0, column=1, padx=5, pady=(5, 10), sticky="ew")

        self.browse_button = ttk.Button(
            self.control_frame, text="Browse...", command=self.browse_file, bootstyle="info-outline"
        )
        self.browse_button.grid(row=0, column=2, padx=(5, 0), pady=(5, 10), sticky="e")

        # --- Region Selection Row ---
        self.region_label = ttk.Label(self.control_frame, text="Select Region:", anchor="w")
        self.region_label.grid(row=1, column=0, padx=(0, 10), pady=(5, 10), sticky="w")

        self.region_options = ["All Regions"] + list(self.regions_data.keys())
        self.selected_region_var = tk.StringVar()

        self.region_combobox = ttk.Combobox(
            self.control_frame,
            textvariable=self.selected_region_var,
            values=self.region_options,
            state='readonly',
            bootstyle=PRIMARY
        )
        if self.region_options:
            self.region_combobox.current(0) # Default to "All Regions"
        else:
            self.region_combobox.config(state='disabled')
            self.selected_region_var.set("No regions configured!")

        self.region_combobox.grid(row=1, column=1, columnspan=2, padx=5, pady=(5, 10), sticky="ew")
        # Bind selection event to update city combobox AND filename
        self.region_combobox.bind("<<ComboboxSelected>>", self.on_region_selected)

        # --- City Selection Row ---
        self.city_label = ttk.Label(self.control_frame, text="Select City:", anchor="w")
        self.city_label.grid(row=2, column=0, padx=(0, 10), pady=(5, 10), sticky="w")

        # City Combobox - Initial state is disabled, populated by region selection
        self.selected_city_var = tk.StringVar()
        self.city_combobox = ttk.Combobox(
            self.control_frame,
            textvariable=self.selected_city_var,
            values=["Select a region first"], # Placeholder
            state='disabled', # Start disabled
            bootstyle=PRIMARY
        )
        self.city_combobox.grid(row=2, column=1, columnspan=2, padx=5, pady=(9, 10), sticky="ew")
        # Bind selection event to update filename
        self.city_combobox.bind("<<ComboboxSelected>>", self.on_city_selected)


        # --- Action Row ---
        self.action_frame = ttk.Frame(self.control_frame)
        self.action_frame.grid(row=3, column=0, columnspan=3, pady=(15, 5), sticky="ew")
        self.action_frame.columnconfigure(0, weight=1) # Center button

        self.start_button = ttk.Button(
            self.action_frame, text="Start Scraping", command=self.start_scraping_thread, bootstyle="success", width=20
        )
        self.start_button.pack(pady=5) # Use pack to center within action_frame


        # --- Log Area ---
        self.log_frame = ttk.LabelFrame(
            self.main_frame, text=" Logs ", padding=10, bootstyle=PRIMARY
        )
        self.log_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 10)) # Adjusted row index
        self.log_frame.rowconfigure(0, weight=1)
        self.log_frame.columnconfigure(0, weight=1)

        initial_bg = self.style.colors.get('bg')
        initial_fg = self.style.colors.get('fg')

        self.log_text = ScrolledText(self.log_frame, padding=5, height=15, autohide=True)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.text.config(background=initial_bg, foreground=initial_fg)

        self.configure_log_tags()

        # --- Status Bar ---
        self.status_frame = ttk.Frame(self.main_frame, padding=(5, 5))
        self.status_frame.grid(row=5, column=0, sticky="ew") # Adjusted row index
        self.status_frame.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready. Select region, city, and output file.")
        self.status_label = ttk.Label(
            self.status_frame, textvariable=self.status_var, bootstyle="secondary", anchor="w"
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

        # Progress bar (hidden initially)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.status_frame, variable=self.progress_var, mode='indeterminate', bootstyle="success-striped"
        )
        # Will be gridded in when needed

        # --- Initialize variables ---
        self.scraping_active = False
        self.all_data = []
        self.scrape_thread = None

        # --- Initialize City Combobox based on default Region ---
        self.on_region_selected() # Trigger initial population AND filename update
        # --- Initial Filename Update (call again ensures city is considered) ---
        self._update_default_filename()


    def _load_theme_preference(self):
        """Loads the theme name from the settings file, returns default if not found/invalid."""
        default = DEFAULT_DARK_THEME
        try:
            theme_file = THEME_SETTINGS_FILE # Use the variable defined/imported
            if os.path.exists(theme_file):
                with open(theme_file, 'r') as f:
                    theme_name = f.read().strip()
                if theme_name in [DEFAULT_DARK_THEME, DEFAULT_LIGHT_THEME]:
                    print(f"INFO: Loaded theme preference: {theme_name}")
                    return theme_name
                else:
                    print(f"WARN: Invalid theme '{theme_name}' found in {os.path.basename(theme_file)}. Using default.")
            else:
                 pass # Silently use default if no file
        except Exception as e:
            print(f"WARN: Error reading theme settings file '{os.path.basename(THEME_SETTINGS_FILE)}': {e}. Using default.")
        return default

    def _save_theme_preference(self, theme_name):
        """Saves the given theme name to the settings file."""
        try:
            theme_file = THEME_SETTINGS_FILE # Use the variable defined/imported
            with open(theme_file, 'w') as f:
                f.write(theme_name)
        except Exception as e:
            log_func = getattr(self, 'update_log', print)
            try:
                log_func(f"WARN: Could not save theme setting to '{os.path.basename(theme_file)}': {e}", "WARNING")
            except:
                print(f"WARN: Could not save theme setting to '{os.path.basename(THEME_SETTINGS_FILE)}': {e}")

    def configure_log_tags(self):
        """Configures the tags used for styling text in the log area."""
        colors = self.style.colors
        base_font_family = "Helvetica"
        base_font_size = 10

        tag_configs = {
            'INFO': {'foreground': colors.get('fg')},
            'WARNING': {'foreground': colors.warning},
            'ERROR': {'foreground': colors.danger, 'font': (base_font_family, base_font_size, "bold")},
            'SUCCESS': {'foreground': colors.success},
            'CITY_HEADER': {'foreground': colors.info, 'font': (base_font_family, base_font_size, "bold")},
            'CAPTCHA': {'foreground': colors.primary, 'font': (base_font_family, base_font_size, "bold")}
        }

        for tag, config in tag_configs.items():
            try:
                if self.log_text.winfo_exists(): # Check if widget exists
                    self.log_text.tag_configure(tag, **config)
            except tk.TclError:
                # This can happen during theme change or shutdown, ignore safely
                if "invalid command name" not in str(e).lower():
                     print(f"Warn: Could not configure tag '{tag}' (TclError)")
            except Exception as e:
                 print(f"Warn: Could not configure tag '{tag}' (Error: {e})")


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
                # Don't log theme change here, log_text might be reconfigured
                # self.update_log(f"Theme changed to: {new_theme}", "INFO")
                self._save_theme_preference(new_theme)
                if self.theme_toggle.winfo_exists():
                    self.theme_toggle.config(text=toggle_text)

                # Update log area colors AFTER theme change
                new_bg = self.style.colors.get('bg')
                new_fg = self.style.colors.get('fg')
                if self.log_text.winfo_exists():
                    self.log_text.text.config(background=new_bg, foreground=new_fg)
                # Reconfigure tags for new colors
                self.configure_log_tags()
                 # Log the theme change now
                print(f"INFO: Theme changed to: {new_theme}") # Use print as log might not be ready
                self.root.after(50, lambda: self.update_log(f"Theme changed to: {new_theme}", "INFO")) # Delay log slightly
            else:
                 if self.theme_toggle.winfo_exists():
                    self.theme_toggle.config(text=toggle_text)
        except tk.TclError as e:
             # Safely handle errors during theme change (e.g., widget destroyed)
             if "invalid command name" not in str(e).lower():
                 print(f"Error changing theme: {e}")
                 try:
                     # Try logging with a delay if update_log is available
                     if hasattr(self, 'update_log'):
                          self.root.after(50, lambda: self.update_log(f"Error changing theme: {e}", "ERROR"))
                 except: pass # Ignore if logging fails too


    def _update_default_filename(self):
        """Updates the filename entry based on region/city selections."""
        try:
            selected_region = self.selected_region_var.get()
            selected_city_option = self.selected_city_var.get()

            # Get current path parts to preserve directory and extension
            current_full_path = self.filename_var.get()
            current_dir = os.path.dirname(current_full_path) or self.initial_output_dir
            current_ext = os.path.splitext(current_full_path)[1] or self.initial_output_ext

            # Determine filename components
            region_part = "AllRegions"
            city_part = "AllCities"

            if selected_region and selected_region != "All Regions" and selected_region != "No regions configured!":
                region_part = _sanitize_filename_part(selected_region)
                all_cities_label = f"All Cities in {selected_region}"
                if selected_city_option and selected_city_option != all_cities_label and selected_city_option != "Select a region first":
                    city_part = _sanitize_filename_part(selected_city_option)
                elif selected_city_option == all_cities_label:
                     city_part = "AllCities"
                else: # No city selected yet for this region
                     city_part = "" # Or maybe keep "AllCities"? Let's use empty for clarity.

            elif selected_region == "All Regions":
                 # City part is already "AllCities", region part is "AllRegions"
                 pass

            elif selected_region == "No regions configured!":
                 region_part = "NoRegion"
                 city_part = "NoCity"

            # Construct the new base filename
            if region_part and city_part:
                new_base = f"{self.initial_output_base}_{region_part}_{city_part}"
            elif region_part:
                new_base = f"{self.initial_output_base}_{region_part}"
            else: # Should not happen often, fallback
                new_base = f"{self.initial_output_base}_Selection"

            # Combine parts
            new_filename = os.path.join(current_dir, new_base + current_ext)

            # Update the entry widget
            self.filename_var.set(new_filename)

        except Exception as e:
            print(f"Error updating default filename: {e}")
            # Optionally log to GUI if available
            # self.update_log(f"WARN: Could not update filename suggestion: {e}", "WARNING")


    def on_region_selected(self, event=None):
        """Handles region selection change, updates city combobox and filename."""
        selected_region = self.selected_region_var.get()
        # print(f"DEBUG: Region selected: {selected_region}") # Debug print

        # Always reset city selection first
        self.selected_city_var.set("")

        # Check if widgets exist before configuring
        if not hasattr(self, 'city_combobox') or not self.city_combobox.winfo_exists():
            print("WARN: City combobox does not exist during region selection.")
            return # Don't update filename if city box is gone

        if selected_region == "All Regions":
            new_city_options = ["All Cities"]
            self.city_combobox.config(values=new_city_options, state='readonly')
            if new_city_options:
                self.selected_city_var.set(new_city_options[0])
        elif selected_region in self.regions_data:
            cities = self.regions_data[selected_region]
            # Create a sorted list with "All Cities in..." first
            all_cities_label = f"All Cities in {selected_region}"
            new_city_options = [all_cities_label] + sorted(cities) # Sort cities alphabetically
            self.city_combobox.config(values=new_city_options, state='readonly')
            if new_city_options:
                self.selected_city_var.set(new_city_options[0]) # Default to "All Cities in..."
        else: # No region selected or invalid region (or config empty)
            self.city_combobox.config(values=["Select a region first"], state='disabled')

        # Update the filename based on the new selections
        self._update_default_filename()


    def on_city_selected(self, event=None):
        """Handles city selection change, updates filename."""
        # print(f"DEBUG: City selected: {self.selected_city_var.get()}") # Debug print
        self._update_default_filename()


    def browse_file(self):
        """Opens a file dialog to select the save location and filename."""
        # Suggest a filename based on current selections
        self._update_default_filename() # Ensure suggestion is up-to-date
        suggested_filename = self.filename_var.get()

        initial_dir = os.path.dirname(suggested_filename)
        initial_file = os.path.basename(suggested_filename)

        filetypes = [("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]

        filepath = filedialog.asksaveasfilename(
            title="Save Scraped Data As",
            initialdir=initial_dir,
            initialfile=initial_file,
            defaultextension=".xlsx", # Keep default ext
            filetypes=filetypes,
            parent=self.root
        )

        if filepath:
            # Simple check to add default extension if user removed it
            # but selected type (less reliable without knowing chosen type)
            root_ext, ext = os.path.splitext(filepath)
            if not ext:
                 # Default to .xlsx if no extension is provided by user
                 filepath += ".xlsx"


            self.filename_var.set(filepath)
            self.update_log(f"Output file set to: {filepath}", "INFO")
            # Note: We don't call _update_default_filename() here,
            # because the user explicitly chose a path. If they change
            # region/city *after* browsing, _update_default_filename
            # will run and use the new path's directory and extension.


    def update_log(self, message, level="INFO"):
        """Safely appends a message to the log area from any thread with optional level tagging."""
        def _append():
            if not self.root or not self.root.winfo_exists() or not hasattr(self, 'log_text') or not self.log_text.winfo_exists():
                 print(f"Log Error: GUI element destroyed. Msg: {message}")
                 return

            try:
                tag = level.upper() if level.upper() in ['INFO', 'WARNING', 'ERROR', 'SUCCESS', 'CITY_HEADER', 'CAPTCHA'] else 'INFO'

                msg_upper = message.upper()
                # Auto-tagging logic (optional enhancement)
                if tag == 'INFO':
                     if "=== BẮT ĐẦU" in message or "=== HOÀN THÀNH" in message or "===" in message or "---" in message: tag = 'CITY_HEADER'
                     elif "ĐÃ LƯU XONG" in message or "✅" in message or "SAVED" in msg_upper or "SUCCESS" in msg_upper: tag = 'SUCCESS'
                     elif "CAPTCHA" in msg_upper: tag = 'CAPTCHA'
                     elif "WARN" in msg_upper or "CẢNH BÁO" in msg_upper or "⚠️" in message: tag = 'WARNING'
                     elif "ERROR" in msg_upper or "LỖI" in msg_upper or "FAIL" in msg_upper or "❌" in message or "!!!" in message: tag = 'ERROR'

                # Ensure the tag exists (and reconfigure if needed after theme change)
                if tag not in self.log_text.tag_names():
                    try: self.configure_log_tags() # Attempt reconfiguration
                    except: pass # Ignore if reconfiguration fails
                    # If tag still doesn't exist, use INFO
                    if tag not in self.log_text.tag_names():
                         print(f"Log Warning: Tag '{tag}' not configured. Using 'INFO'.")
                         tag = 'INFO' # Fallback tag

                self.log_text.insert(tk.END, message + '\n', (tag,))
                self.log_text.see(tk.END) # Scroll to the end
            except tk.TclError as e:
                 if "invalid command name" not in str(e).lower():
                      print(f"Log Error (TclError): {e}. Msg: {message}")
            except Exception as e:
                 print(f"Log Error (Exception): {e}. Msg: {message}")
                 traceback.print_exc()

        if hasattr(self.root, 'after'):
            try:
                 # Use after_idle for potentially better responsiveness during heavy logging
                 self.root.after_idle(_append)
            except tk.TclError:
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

        if hasattr(self.root, 'after'):
            try:
                 # Use after_idle for potentially better responsiveness
                 self.root.after_idle(_update)
            except tk.TclError:
                 print(f"Status Error: Window destroyed before scheduling. Msg: {message}")


    def start_scraping_thread(self):
        """Starts the scraping process in a new thread."""
        if self.scraping_active:
            Messagebox.show_warning("Scraping is already in progress.", "Busy", parent=self.root)
            return

        # Ensure the filename is updated one last time before starting
        self._update_default_filename()
        output_file = self.filename_var.get().strip()
        selected_region = self.selected_region_var.get().strip()
        selected_city_option = self.selected_city_var.get().strip()

        # --- Input Validations ---
        if not output_file:
            Messagebox.show_error("Please specify an output filename.", "Error", parent=self.root)
            return

        if not selected_region or selected_region == "No regions configured!":
            Messagebox.show_error("Please select a region.", "Error", parent=self.root)
            return

        if not selected_city_option or selected_city_option == "Select a region first":
            Messagebox.show_error("Please select a city (after selecting a region).", "Error", parent=self.root)
            return

        # --- Directory and Permissions Validation ---
        output_dir = os.path.dirname(output_file)
        if not output_dir: # If only filename is given, use current dir
            output_dir = os.getcwd()
            output_file = os.path.join(output_dir, os.path.basename(output_file))
            # Update the entry box if we modified the path
            self.filename_var.set(output_file)

        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.update_log(f"Created output directory: {output_dir}", level="INFO")
            except OSError as e:
                Messagebox.show_error(f"Could not create directory:\n{output_dir}\nError: {e}", "Directory Error", parent=self.root)
                self.update_log(f"Directory creation failed: {e}", level="ERROR")
                return

        # Check write permissions AFTER potentially creating the directory
        if not os.access(output_dir, os.W_OK):
            Messagebox.show_error(f"Cannot write to directory:\n{output_dir}\nCheck permissions.", "Permission Error", parent=self.root)
            self.update_log(f"Write permission denied for directory: {output_dir}", level="ERROR")
            return

        # --- File Extension Validation ---
        allowed_extensions = [".xlsx", ".csv"]
        file_root, file_ext = os.path.splitext(output_file)
        file_ext = file_ext.lower()

        # Ensure file has an allowed extension, correcting if necessary
        if file_ext not in allowed_extensions:
             # Default to .xlsx if extension is missing or invalid
             new_output_file = file_root + ".xlsx"
             self.update_log(f"WARN: Invalid or missing extension '{file_ext}'. Changing filename to '{os.path.basename(new_output_file)}'.", level="WARNING")
             self.filename_var.set(new_output_file)
             output_file = new_output_file # Use the corrected filename


        # --- Start Scraping ---
        self.scraping_active = True
        self.toggle_controls(enabled=False)

        self.progress_bar.grid(row=0, column=1, padx=(10, 0), sticky="e") # Ensure progress bar is in status bar
        self.progress_bar.start(10)

        # More descriptive start message
        if selected_region == "All Regions":
            scrape_target_desc = "ALL Regions"
        elif selected_city_option.startswith("All Cities in"):
            scrape_target_desc = f"ALL Cities in {selected_region}"
        else:
            scrape_target_desc = f"City: {selected_city_option} in Region: {selected_region}"

        self.update_status(f"Starting scraper for: {scrape_target_desc}...")
        self.log_text.delete('1.0', tk.END)
        self.all_data = []

        self.scrape_thread = threading.Thread(
            target=self.run_scraping_task,
            args=(selected_region, selected_city_option), # Pass both region and city
            daemon=True
        )
        self.scrape_thread.start()


    def toggle_controls(self, enabled=True):
        """Enable or disable input controls."""
        state = tk.NORMAL if enabled else tk.DISABLED
        readonly_state = 'readonly' if enabled else tk.DISABLED

        widgets_to_toggle = [
            (self.start_button, state),
            (self.browse_button, state),
            (self.filename_entry, tk.NORMAL if enabled else tk.DISABLED), # Entry is editable
            (self.region_combobox, readonly_state if enabled and self.selected_region_var.get() != "No regions configured!" else tk.DISABLED),
            (self.theme_toggle, state)
        ]

        # Special handling for city combobox based on region selection and enabled state
        city_state = tk.DISABLED
        if enabled:
            selected_region = self.selected_region_var.get()
            if selected_region and selected_region != "No regions configured!" and self.selected_city_var.get() != "Select a region first":
                 city_state = readonly_state # Enable if region is selected and controls are enabled

        widgets_to_toggle.append((self.city_combobox, city_state))

        for widget, widget_state in widgets_to_toggle:
            try:
                if widget.winfo_exists():
                    widget.config(state=widget_state)
            except tk.TclError: pass # Ignore errors during shutdown/theme change


    def run_scraping_task(self, selected_region, selected_city_option):
        """The function executed by the worker thread."""
        start_time = time.time()
        self.update_log(f"=== BẮT ĐẦU SCRAPE TASK ===", level="CITY_HEADER")

        total_results_overall = 0
        cities_processed = 0
        cities_with_errors = 0
        cities_with_captcha_block = 0

        try:
            # --- Determine the list of cities to scrape ---
            cities_to_scrape = []
            log_msg_prefix = ""

            if selected_region == "All Regions":
                if selected_city_option == "All Cities":
                    all_cities = []
                    for region, cities in self.regions_data.items():
                        all_cities.extend(cities)
                    cities_to_scrape = sorted(list(set(all_cities))) # Get unique, sorted list
                    if not cities_to_scrape:
                         log_msg_prefix = "--- Mode: Scraping ALL Regions, but no cities found in config ---"
                    else:
                         log_msg_prefix = f"--- Mode: Scraping ALL {len(cities_to_scrape)} unique cities in ALL regions ---"
                else:
                    # This case shouldn't be reachable if GUI logic is correct
                    self.update_log(f"ERROR: Invalid combination: 'All Regions' selected with specific city '{selected_city_option}'. Aborting.", "ERROR")
                    self.root.after(0, self.on_scraping_complete, 0, 1, 0, 0, "Invalid Selection") # Report error
                    return

            elif selected_region in self.regions_data:
                region_cities = self.regions_data[selected_region]
                all_cities_label = f"All Cities in {selected_region}"

                if selected_city_option == all_cities_label:
                    cities_to_scrape = sorted(list(region_cities)) # Get sorted list for the region
                    if not cities_to_scrape:
                        log_msg_prefix = f"--- Mode: Scraping ALL cities in '{selected_region}', but region has no cities listed ---"
                    else:
                        log_msg_prefix = f"--- Mode: Scraping ALL {len(cities_to_scrape)} cities in region: {selected_region} ---"
                elif selected_city_option in region_cities:
                    cities_to_scrape = [selected_city_option]
                    log_msg_prefix = f"--- Mode: Scraping selected city: '{selected_city_option}' in region: {selected_region} ---"
                else:
                    # Invalid city for the selected region
                    self.update_log(f"ERROR: City '{selected_city_option}' not found in selected region '{selected_region}'. Check config. Aborting.", "ERROR")
                    self.root.after(0, self.on_scraping_complete, 0, 1, 0, 0, "Invalid City") # Report error
                    return
            else:
                 # Invalid region selected (shouldn't happen with combobox)
                 self.update_log(f"ERROR: Invalid region '{selected_region}' selected. Aborting.", "ERROR")
                 self.root.after(0, self.on_scraping_complete, 0, 1, 0, 0, "Invalid Region") # Report error
                 return

            # --- Log the mode and start scraping loop ---
            self.update_log(log_msg_prefix, level="INFO")
            num_cities = len(cities_to_scrape)

            if num_cities == 0:
                self.update_log("No cities to scrape based on selection.", level="WARNING")
                # Pass scrape_outcome="No Cities Found"
                self.root.after(0, self.on_scraping_complete, 0, 0, 0, 0, "No Cities Found")
                return

            # --- Get Final Output Filename (set before loop starts) ---
            # Use after() to ensure it runs on the main thread
            final_output_file_container = []
            def get_filename():
                final_output_file_container.append(self.filename_var.get())
            self.root.after(0, get_filename)
            # Wait briefly for the filename to be retrieved (might be needed)
            time.sleep(0.1)
            if not final_output_file_container:
                self.update_log("ERROR: Could not retrieve final output filename from GUI.", "ERROR")
                self.root.after(0, self.on_scraping_complete, 0, 1, 0, 0, "Filename Error")
                return
            final_output_file = final_output_file_container[0]
            self.update_log(f"--- Target output file: {os.path.basename(final_output_file)} ---", "INFO")


            for city_index, city in enumerate(cities_to_scrape):
                if not self.scraping_active:
                     self.update_log(f"Scraping aborted before processing {city}.", "WARNING")
                     break

                city_start_time = time.time()
                status_msg = f"Scraping city {city_index + 1}/{num_cities}: {city}..."
                self.update_status(status_msg)
                self.update_log(f"\n--- Starting city: {city} ({city_index + 1}/{num_cities}) ---", level="INFO")

                city_data_list = []
                city_status = "UNKNOWN"

                try:
                    if 'scrape_city' in globals() and callable(scrape_city):
                        # Optional short pause before scraping
                        # short_pause = random.uniform(0.5, 1.5)
                        # time.sleep(short_pause)

                        city_data_list, city_status = scrape_city(city, self.update_log)
                    else:
                        self.update_log(f"[{city}] ERROR: Scraper function 'scrape_city' is not available.", "ERROR")
                        city_status = "ERROR"
                        city_data_list = []

                    # Process results based on status
                    if city_status == "OK":
                        if city_data_list:
                            self.all_data.extend(city_data_list)
                            count = len(city_data_list)
                            total_results_overall += count
                            self.update_log(f"[{city}] ✅ Success: Found {count} results. Total collected: {total_results_overall}.", level="SUCCESS")
                        else:
                            self.update_log(f"[{city}] ℹ️ Completed: No results found for this city.", level="INFO")
                            city_status = "NO_RESULTS" # Ensure status reflects no results found
                    elif city_status == "CAPTCHA_EARLY":
                        self.update_log(f"[{city}] ⚠️ Blocked by CAPTCHA at search level. Skipping city.", level="CAPTCHA")
                        cities_with_captcha_block += 1
                    elif city_status == "NO_RESULTS":
                         self.update_log(f"[{city}] ℹ️ Scraper reported no results found.", level="INFO")
                    elif city_status == "ERROR":
                         log_content = self.log_text.get("1.0", tk.END)
                         missing_func_msg = f"ERROR: Scraper function 'scrape_city' is not available."
                         # Only log generic error if specific 'not available' msg isn't already there
                         if missing_func_msg not in log_content:
                              self.update_log(f"[{city}] ❌ Scraper reported an ERROR. Check logs above.", level="ERROR")
                         cities_with_errors += 1
                    else: # Unknown status
                        self.update_log(f"[{city}] ❓ Unknown status from scraper: '{city_status}'. Treating as error.", level="WARNING")
                        cities_with_errors += 1

                except Exception as e_city_run:
                    self.update_log(f"!!! CRITICAL ERROR while running scrape_city for {city} !!!", level="ERROR")
                    self.update_log(traceback.format_exc(), level="ERROR")
                    cities_with_errors += 1
                    city_status = "CRITICAL_ERROR" # Mark specific status
                finally:
                    cities_processed += 1
                    city_end_time = time.time()
                    self.update_log(f"=== Finished {city} in {city_end_time - city_start_time:.2f}s (Status: {city_status}) ===", level="CITY_HEADER")

                # Pause between cities if scraping multiple
                if num_cities > 1 and city_index < num_cities - 1 and self.scraping_active:
                    pause_duration = random.uniform(3.0, 7.0)
                    self.update_status(f"Pausing for {pause_duration:.1f}s before next city...")
                    self.update_log(f"--- Pausing for {pause_duration:.1f} seconds ---", level="INFO")
                    time.sleep(pause_duration)

            scrape_outcome = "Completed"
            if not self.scraping_active:
                 scrape_outcome = "Aborted"
                 self.update_log("--- Scraping aborted by user or error ---", "WARNING")

            # Pass the final output file determined before the loop
            self.root.after(0, self.on_scraping_complete, cities_processed, cities_with_errors, cities_with_captcha_block, total_results_overall, scrape_outcome, final_output_file)

        except Exception as e_thread:
            self.update_log(f"!!! CRITICAL ERROR IN MAIN SCRAPING THREAD !!!", level="ERROR")
            self.update_log(traceback.format_exc(), level="ERROR")
            # Pass error outcome and try to get filename if possible
            error_filename = "unknown_file_error.xlsx"
            try:
                error_filename = self.filename_var.get() # Get current filename on error
            except: pass
            self.root.after(0, self.on_scraping_error, f"Critical error in thread loop: {e_thread}", error_filename)

        finally:
            end_time = time.time()
            total_duration = end_time - start_time
            self.update_log(f"\n=== SCRAPING THREAD FINISHED IN {total_duration:.2f} seconds ({total_duration/60:.2f} minutes) ===", level="INFO")


    def on_scraping_complete(self, cities_processed, cities_with_errors, cities_with_captcha_block, total_results_found, scrape_outcome, final_output_file):
        """Tasks to run in the main thread after scraping loop finishes."""
        try:
            if self.progress_bar.winfo_exists():
                self.progress_bar.stop()
                self.progress_bar.grid_forget()
        except tk.TclError: pass

        self.update_status("Scraping finished. Processing and saving results...")
        self.update_log("\n--- Processing and Saving Results ---", level="CITY_HEADER")

        # Use the filename passed from the scraping thread
        output_file = final_output_file
        export_successful = False
        final_save_path = output_file # Assume this path initially
        saved_format = ""
        actual_saved_count = 0

        # Handle early aborts or specific non-saving outcomes
        if scrape_outcome in ["Invalid Selection", "Invalid City", "Invalid Region", "Filename Error"]:
             self.update_log(f"Scraping aborted early due to error: {scrape_outcome}. No data to save.", "ERROR")
             self.update_status(f"Error: {scrape_outcome}. Scraping stopped.")
             self.scraping_active = False
             self.toggle_controls(enabled=True)
             return
        elif scrape_outcome == "No Cities Found":
            self.update_log("No cities were found to scrape based on the configuration/selection.", "WARNING")
            self.update_status("Completed. No cities found to scrape.")
            self.scraping_active = False
            self.toggle_controls(enabled=True)
            return
        elif scrape_outcome == "Aborted":
            self.update_log("Scraping was aborted. Saving any partially collected data...", "WARNING")
            # Proceed to save any data collected before abort

        # Proceed with saving if data exists or was aborted mid-way
        if self.all_data:
            final_count = len(self.all_data)
            self.update_log(f"Total items collected: {final_count}. Preparing to save to '{os.path.basename(output_file)}'...", level="INFO")

            try:
                df = pd.DataFrame(self.all_data)
                # --- Data Cleaning (Simplified for brevity - Keep your detailed cleaning) ---
                self.update_log("Structuring DataFrame...", level="INFO")
                columns_order = [
                    "Thành phố", "Tên công ty", "Địa chỉ", "Số điện thoại", "Website",
                    "Giờ hoạt động", "Google Maps URL", "Vĩ độ", "Kinh độ", "Notes"
                ]
                for col in columns_order:
                    if col not in df.columns: df[col] = pd.NA
                df = df.reindex(columns=columns_order)

                self.update_log("Cleaning data (filling N/A, stripping whitespace)...", level="INFO")
                # Add your robust cleaning logic back here...
                # (Using a simplified placeholder for this example)
                df.fillna('N/A', inplace=True)
                for col in df.select_dtypes(include=['object']).columns:
                     if col != "Notes": # Don't strip Notes whitespace necessarily
                        df[col] = df[col].astype(str).str.strip()
                        df.loc[df[col] == '', col] = 'N/A' # Replace empty strings after strip
                if "Notes" not in df.columns: df["Notes"] = ""
                df["Notes"] = df["Notes"].fillna("")

                # Final check before saving
                df_to_save = df
                actual_saved_count = len(df_to_save)
                if actual_saved_count == 0:
                    self.update_log("Data collected, but resulted in 0 rows after processing.", level="WARNING")
                    df_to_save = None # Don't attempt to save empty dataframe
                else:
                    self.update_log(f"Data cleaning finished. Attempting to save {actual_saved_count} rows.", level="INFO")

                # --- Saving Logic ---
                save_attempted = False
                file_root, file_ext = os.path.splitext(output_file)
                file_ext = file_ext.lower()

                # Ensure output directory exists (redundant check, but safe)
                output_dir = os.path.dirname(output_file)
                if output_dir and not os.path.exists(output_dir):
                    try: os.makedirs(output_dir)
                    except OSError as e:
                        self.update_log(f"ERROR: Could not create directory just before saving: {e}", "ERROR")
                        Messagebox.showerror("Save Error", f"Could not create directory:\n{output_dir}\nSaving failed.", parent=self.root)
                        df_to_save = None # Prevent save attempt

                if df_to_save is not None:
                    if file_ext == ".xlsx":
                        try:
                            save_attempted = True
                            df_to_save.to_excel(output_file, index=False, engine='openpyxl')
                            self.update_log(f"\n✅ Successfully saved data to Excel: '{os.path.basename(output_file)}'", level="SUCCESS")
                            export_successful = True
                            final_save_path = output_file
                            saved_format = "Excel"
                        except ImportError:
                             self.update_log("\n❌ ERROR: 'openpyxl' library not found (required for .xlsx). Install: pip install openpyxl", level="ERROR")
                             Messagebox.show_error("'openpyxl' is required to save Excel (.xlsx) files.\nInstall it using: pip install openpyxl", "Missing Library", parent=self.root)
                        except Exception as e_excel:
                            self.update_log(f"\n❌ ERROR saving Excel file '{os.path.basename(output_file)}': {e_excel}", level="ERROR")
                            self.update_log(traceback.format_exc(), level="ERROR")
                            Messagebox.show_error(f"Failed to save Excel file:\n{e_excel}", "Excel Export Error", parent=self.root)

                    elif file_ext == ".csv":
                        try:
                            save_attempted = True
                            df_to_save.to_csv(output_file, index=False, encoding='utf-8-sig')
                            self.update_log(f"\n✅ Successfully saved data to CSV: '{os.path.basename(output_file)}'", level="SUCCESS")
                            export_successful = True
                            final_save_path = output_file
                            saved_format = "CSV"
                        except Exception as e_csv:
                            self.update_log(f"\n❌ ERROR saving CSV file '{os.path.basename(output_file)}': {e_csv}", level="ERROR")
                            self.update_log(traceback.format_exc(), level="ERROR")
                            Messagebox.show_error(f"Failed to save CSV file:\n{e_csv}", "CSV Export Error", parent=self.root)
                    else:
                         # This case should be less likely now due to pre-start validation
                         self.update_log(f"\n❌ ERROR: Invalid file extension '{file_ext}' detected during save for file '{os.path.basename(output_file)}'. Save failed.", level="ERROR")
                         Messagebox.showerror("Save Error", f"Cannot save file with unsupported extension: {file_ext}", parent=self.root)


                    if not save_attempted and df_to_save is not None:
                         self.update_log("\n⚠️ File saving was not attempted (check directory/permissions logs).", level="WARNING")

            except Exception as e_df:
                 self.update_log(f"\n❌ CRITICAL ERROR during data processing/saving preparation: {e_df}", level="ERROR")
                 self.update_log(traceback.format_exc(), level="ERROR")
                 Messagebox.showerror(f"An error occurred while processing the collected data:\n{e_df}", "Data Processing Error", parent=self.root)
                 export_successful = False # Mark as failed

        else: # No self.all_data
            if scrape_outcome != "Aborted": # Don't show "No data" if user aborted
                self.update_log("\n🤷 No data was collected during the scrape.", level="WARNING")
                if cities_with_errors == 0 and cities_with_captcha_block == 0:
                    Messagebox.showinfo("No Data", "The scraping process completed, but no data was collected or available to save.", parent=self.root)
            export_successful = True # No data is not a failure to save

        # --- Finalize GUI State ---
        if scrape_outcome == "Aborted":
             final_summary_msg = f"Aborted. Processed {cities_processed} cities."
        else:
             final_summary_msg = f"Completed. Processed {cities_processed} cities."

        if export_successful :
             if self.all_data and saved_format and actual_saved_count > 0:
                  final_summary_msg += f" Saved {actual_saved_count} rows to {os.path.basename(final_save_path)} ({saved_format})."
             elif not self.all_data and scrape_outcome != "Aborted": # Only mention no data if not aborted
                  final_summary_msg += " No data collected."
             elif self.all_data and (not saved_format or not export_successful): # Check if saving failed despite having data
                  final_summary_msg += f" Failed to save {len(self.all_data)} results. Check logs."
        elif self.all_data: # If export failed but we had data
             final_summary_msg = f"Completed with errors. Processed {cities_processed} cities. Failed to save {len(self.all_data)} results."

        status_notes = []
        if cities_with_captcha_block > 0: status_notes.append(f"{cities_with_captcha_block} cities CAPTCHA blocked")
        if cities_with_errors > 0: status_notes.append(f"{cities_with_errors} cities had errors")
        if status_notes: final_summary_msg += f" ({'; '.join(status_notes)})."

        self.update_status(final_summary_msg)

        # --- Cleanup ---
        self.scraping_active = False
        self.toggle_controls(enabled=True)
        self._update_default_filename() # Update filename for next run


    def on_scraping_error(self, error_message, filename_on_error):
        """Tasks to run in the main thread if a critical error occurred in the thread loop."""
        try:
            if self.progress_bar.winfo_exists():
                self.progress_bar.stop()
                self.progress_bar.grid_forget()
        except tk.TclError: pass

        self.update_log(f"\n--- SCRAPING HALTED DUE TO CRITICAL ERROR ---", level="ERROR")
        self.update_status(f"Critical Error: Scraping stopped. Check logs.")
        Messagebox.showerror(f"A critical error stopped the process:\n{error_message}\n\nPlease check the logs for details.", "Scraping Error", parent=self.root)

        # Attempt to save any partial data collected before the critical error
        if self.all_data:
             self.update_log(f"Attempting to save partial data ({len(self.all_data)} items) due to error...", "WARNING")
             # Call a simplified save routine or reuse parts of on_scraping_complete's save block
             # For simplicity, we'll just log it here, but you could trigger a save attempt.
             # self.save_data_emergency(filename_on_error) # Hypothetical function
             pass # For now, just rely on logs

        self.scraping_active = False
        self.toggle_controls(enabled=True)
        self._update_default_filename() # Update filename


# --- Main Execution ---
if __name__ == "__main__":
    initial_theme = DEFAULT_DARK_THEME
    try:
        theme_file = THEME_SETTINGS_FILE # Use defined variable
        if os.path.exists(theme_file):
            with open(theme_file, 'r') as f:
                theme_name = f.read().strip()
            if theme_name in [DEFAULT_DARK_THEME, DEFAULT_LIGHT_THEME]:
                initial_theme = theme_name
    except Exception as e:
        print(f"WARN: Could not preload theme setting: {e}")

    root = ttk.Window(themename=initial_theme)
    app = ScraperApp(root)

    def on_closing():
        if app.scraping_active:
            if Messagebox.askyesno("Quit", "Scraping is active. Quit anyway?\n(This may corrupt the save file if currently writing)", parent=root):
                print("Attempting abrupt shutdown...")
                app.scraping_active = False # Try to signal thread
                # Optionally add more forceful thread stopping if needed
                root.destroy()
            else:
                return # Don't close
        else:
             print("Closing application.")
             root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()