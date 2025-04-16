# gmaps_scraper_project/gui.py

# -*- coding: utf-8 -*-
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledText
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
    # Define a dummy function to prevent immediate crash if scraper is missing
    def scrape_city(city, logger_callback):
        logger_callback(f"ERROR: Scraper function 'scrape_city' not found for {city}.", "ERROR")
        return [], "ERROR"


# --- GUI Application Class ---
class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Maps Scraper - Self Storage Australia")
        self.root.geometry("850x700")  # Slightly larger for better readability
        
        # Set the theme
        self.theme_name = "darkly"  # A clean, modern theme
        
        # --- Frames ---
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=BOTH, expand=YES)
        
        # Header with title and description
        self.header_frame = ttk.Frame(self.main_frame)
        self.header_frame.pack(fill=X, pady=(0, 10))
        
        self.title_label = ttk.Label(
            self.header_frame, 
            text="Google Maps Scraper", 
            font=("Helvetica", 16, "bold"),
            bootstyle="dark"
        )
        self.title_label.pack(side=LEFT, padx=5)
        
        self.subtitle_label = ttk.Label(
            self.header_frame, 
            text="Self Storage Australia", 
            font=("Helvetica", 12),
            bootstyle="secondary"
        )
        self.subtitle_label.pack(side=LEFT, padx=5, pady=5)

        # Control frame for user inputs
        self.control_frame = ttk.LabelFrame(
            self.main_frame, 
            text="Scraper Settings", 
            padding=15,
            bootstyle="primary"
        )
        self.control_frame.pack(fill=X, pady=(0, 10))

        # File selection area
        self.file_row_frame = ttk.Frame(self.control_frame)
        self.file_row_frame.pack(fill=X, pady=(5, 10))

        self.filename_label = ttk.Label(
            self.file_row_frame, 
            text="Output File:",
            width=15,
            bootstyle="primary"
        )
        self.filename_label.pack(side=LEFT, padx=(5, 10))

        self.filename_var = tk.StringVar(value=DEFAULT_OUTPUT_FILENAME)
        self.filename_entry = ttk.Entry(
            self.file_row_frame, 
            textvariable=self.filename_var, 
            width=50,
            bootstyle="primary"
        )
        self.filename_entry.pack(side=LEFT, padx=5, fill=X, expand=YES)

        self.browse_button = ttk.Button(
            self.file_row_frame, 
            text="Browse...", 
            command=self.browse_file,
            bootstyle="outline"
        )
        self.browse_button.pack(side=LEFT, padx=5)

        # City selection area
        self.action_row_frame = ttk.Frame(self.control_frame)
        self.action_row_frame.pack(fill=X, pady=(0, 5))

        self.city_label = ttk.Label(
            self.action_row_frame, 
            text="Select or Enter City:",
            width=15,
            bootstyle="primary"
        )
        self.city_label.pack(side=LEFT, padx=(5, 10))

        # Prepare city options for the combobox
        self.config_cities = CITIES if isinstance(CITIES, list) else []
        self.city_options = ["All Cities"] + self.config_cities
        self.selected_city_var = tk.StringVar()

        self.city_combobox = ttk.Combobox(
            self.action_row_frame,
            textvariable=self.selected_city_var,
            values=self.city_options,
            state='normal',
            width=25,
            bootstyle="primary"
        )
        # Set default selection only if options exist
        if self.city_options:
            self.city_combobox.current(0)  # Default to "All Cities"
        else:
            # Handle case where CITIES list might be empty in config
            self.city_combobox.config(state='disabled')
            self.selected_city_var.set("No cities configured!")

        self.city_combobox.pack(side=LEFT, padx=5)

        # Start button with accent style
        self.start_button = ttk.Button(
            self.action_row_frame, 
            text="Start Scraping", 
            command=self.start_scraping_thread,
            bootstyle="success"
        )
        self.start_button.pack(side=RIGHT, padx=(10, 5))

        # Log area
        self.log_frame = ttk.LabelFrame(
            self.main_frame, 
            text="Logs", 
            padding=10,
            bootstyle="primary"
        )
        self.log_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        self.log_text = ScrolledText(
            self.log_frame, 
            padding=5,
            height=20,
            autohide=True,
            bootstyle="primary"
        )
        self.log_text.pack(fill=BOTH, expand=YES)
        
        # Configure text tags for different log levels
        self.log_text.tag_configure('INFO', foreground='black')
        self.log_text.tag_configure('WARNING', foreground='orange')
        self.log_text.tag_configure('ERROR', foreground='red', font=("Helvetica", 10, "bold"))
        self.log_text.tag_configure('SUCCESS', foreground='green')
        self.log_text.tag_configure('CITY_HEADER', foreground='blue', font=("Helvetica", 10, "bold"))
        self.log_text.tag_configure('CAPTCHA', foreground='purple', font=("Helvetica", 10, "bold"))

        # Status bar
        self.status_frame = ttk.Frame(self.main_frame, padding=(5, 5))
        self.status_frame.pack(fill=X, side=BOTTOM)

        self.status_var = tk.StringVar(value="Ready. Select/Enter city and output file.")
        self.status_label = ttk.Label(
            self.status_frame, 
            textvariable=self.status_var, 
            bootstyle="secondary"
        )
        self.status_label.pack(fill=X)

        # Progress bar (hidden initially)
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.status_frame,
            variable=self.progress_var,
            mode='indeterminate',
            bootstyle="success-striped"
        )

        # Initialize variables
        self.scraping_active = False
        self.all_data = []
        self.scrape_thread = None

    def browse_file(self):
        """Opens a file dialog to select the save location and filename."""
        current_path = self.filename_var.get()
        initial_dir = os.path.dirname(current_path) if os.path.dirname(current_path) and os.path.isdir(os.path.dirname(current_path)) else os.getcwd()
        initial_file = os.path.basename(current_path) if current_path else DEFAULT_OUTPUT_FILENAME

        filetypes = [("Excel files", "*.xlsx"), ("CSV files", "*.csv"), ("All files", "*.*")]

        filepath = filedialog = self.root.call('tk_getSaveFile',
            '-title', "Save Scraped Data As",
            '-initialdir', initial_dir,
            '-initialfile', initial_file,
            '-defaultextension', ".xlsx",
            '-filetypes', filetypes
        )
        
        if filepath:
            _, ext = os.path.splitext(filepath)
            if not ext:
                filepath += ".xlsx"
            self.filename_var.set(filepath)

    def update_log(self, message, level="INFO"):
        """Safely appends a message to the log area from any thread with optional level tagging."""
        def _append():
            if not self.root.winfo_exists() or not self.log_text.winfo_exists(): return

            tag = 'INFO'  # Default tag
            msg_upper = message.upper()
            if "ERROR" in level.upper() or "LỖI" in msg_upper or "FAIL" in msg_upper : tag = 'ERROR'
            elif "WARN" in level.upper() or "CẢNH BÁO" in msg_upper : tag = 'WARNING'
            elif "SUCCESS" in level.upper() or "ĐÃ LƯU XONG" in message or "✅" in message or "SAVED" in msg_upper: tag = 'SUCCESS'
            elif "=== BẮT ĐẦU" in message or "=== HOÀN THÀNH" in message or "===" in message: tag = 'CITY_HEADER'
            elif "CAPTCHA" in message.upper(): tag = 'CAPTCHA'

            self.log_text.insert(tk.END, message + '\n', (tag,))
            self.log_text.see(tk.END)
        
        if self.root.winfo_exists():
            self.root.after(0, _append)

    def update_status(self, message):
        """Safely updates the status bar from any thread."""
        def _update():
            if not self.root.winfo_exists() or not hasattr(self, 'status_var'): return
            self.status_var.set(message)
        
        if self.root.winfo_exists():
            self.root.after(0, _update)

    def start_scraping_thread(self):
        """Starts the scraping process in a new thread based on selected/entered city."""
        if self.scraping_active:
            ttk.dialogs.Messagebox.show_warning(
                "Scraping is already in progress.",
                "Busy",
                parent=self.root
            )
            return

        output_file = self.filename_var.get().strip()
        selected_city_option = self.selected_city_var.get().strip()

        if not output_file:
            ttk.dialogs.Messagebox.show_error(
                "Please specify an output filename.",
                "Error",
                parent=self.root
            )
            return
        
        if not selected_city_option or selected_city_option == "No cities configured!":
            ttk.dialogs.Messagebox.show_error(
                "Please select or enter a city name.",
                "Error",
                parent=self.root
            )
            return

        # Validate output directory
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                self.update_log(f"Created output directory: {output_dir}", level="INFO")
            except OSError as e:
                ttk.dialogs.Messagebox.show_error(
                    f"Could not create directory:\n{output_dir}\nError: {e}",
                    "Directory Error",
                    parent=self.root
                )
                self.update_log(f"Directory creation failed: {e}", level="ERROR")
                return
        elif not output_dir:
            output_file = os.path.join(os.getcwd(), output_file)
            self.filename_var.set(output_file)

        save_dir = os.path.dirname(output_file)
        if not os.access(save_dir, os.W_OK):
            ttk.dialogs.Messagebox.show_error(
                f"Cannot write to directory:\n{save_dir}\nCheck permissions.",
                "Permission Error",
                parent=self.root
            )
            self.update_log(f"Write permission denied for directory: {save_dir}", level="ERROR")
            return

        # Validate file extension
        allowed_extensions = [".xlsx", ".csv"]
        file_ext = os.path.splitext(output_file)[1].lower()
        if file_ext not in allowed_extensions:
            confirmed = ttk.dialogs.Messagebox.show_question(
                f"Filename '{os.path.basename(output_file)}' doesn't end with .xlsx or .csv.\nSave might fail or use CSV.\nContinue?",
                "Filename Warning",
                parent=self.root
            )
            if not confirmed: return

        # Start scraping process
        self.scraping_active = True
        
        # Disable controls
        self.start_button.config(state='disabled')
        self.browse_button.config(state='disabled')
        self.filename_entry.config(state='disabled')
        self.city_combobox.config(state='disabled')

        # Start progress bar
        self.progress_bar.pack(fill=X, pady=(5, 0))
        self.progress_bar.start(10)

        # Update status and clear log
        self.update_status(f"Starting scraper for: '{selected_city_option}'...")
        self.log_text.delete('1.0', tk.END)
        self.all_data = []

        # Start scraping thread
        self.scrape_thread = threading.Thread(
            target=self.run_scraping_task, 
            args=(selected_city_option,), 
            daemon=True
        )
        self.scrape_thread.start()

    def run_scraping_task(self, selected_city_option):
        """The function executed by the worker thread, using the selected or entered city option."""
        start_time = time.time()
        self.update_log(f"=== BẮT ĐẦU SCRAPE CHO: '{selected_city_option}' ===", level="CITY_HEADER")

        total_results_overall = 0
        cities_processed = 0
        cities_with_errors = 0
        cities_with_captcha_block = 0

        try:
            # Determine which cities to scrape based on the selection/input
            all_config_cities = self.config_cities

            if selected_city_option == "All Cities":
                if not all_config_cities:
                    self.update_log("LỖI: Đã chọn 'All Cities' nhưng danh sách 'CITIES' trong config.py trống.", level="ERROR")
                    self.root.after(0, self.on_scraping_complete, 0, 0, 0, 0)
                    return
                cities_to_scrape = all_config_cities
                self.update_log(f"--- Chế độ: Scrape TẤT CẢ {len(cities_to_scrape)} thành phố từ config ---", level="INFO")
            else:
                cities_to_scrape = [selected_city_option]
                if selected_city_option in all_config_cities:
                    self.update_log(f"--- Chế độ: Scrape thành phố được chọn: {selected_city_option} ---", level="INFO")
                else:
                    self.update_log(f"--- Chế độ: Scrape thành phố được nhập thủ công: {selected_city_option} ---", level="INFO")

            num_cities = len(cities_to_scrape)
            if num_cities == 0:
                self.update_log("Không có thành phố nào để scrape.", level="WARNING")
                self.root.after(0, self.on_scraping_complete, 0, 0, 0, 0)
                return

            # Process each city
            for city_index, city in enumerate(cities_to_scrape):
                city_start_time = time.time()
                self.update_status(f"Scraping city {city_index + 1}/{num_cities}: {city}...")
                
                # Update progress bar
                progress_value = (city_index / num_cities) * 100
                self.root.after(0, lambda v=progress_value: self.progress_var.set(v))
                
                city_data_list = []
                city_status = "UNKNOWN"

                try:
                    if 'scrape_city' in globals() and callable(scrape_city):
                        city_data_list, city_status = scrape_city(city, self.update_log)
                    else:
                        self.update_log(f"[{city}] LỖI: Hàm scrape_city không tồn tại hoặc không thể gọi.", "ERROR")
                        city_status = "ERROR"
                        city_data_list = []

                    # Process results
                    if city_status == "OK":
                        if city_data_list:
                            self.all_data.extend(city_data_list)
                            count = len(city_data_list)
                            total_results_overall += count
                            captcha_notes_count = sum(1 for item in city_data_list if item.get("Notes") == "CAPTCHA Blocked")
                            error_notes_count = sum(1 for item in city_data_list if "Error" in item.get("Notes", ""))
                            log_detail = f"{count} kết quả"
                            if captcha_notes_count > 0: log_detail += f" ({captcha_notes_count} CAPTCHA)"
                            if error_notes_count > 0: log_detail += f" ({error_notes_count} errors)"
                            self.update_log(f"[{city}] ✅ Thêm {log_detail}. Tổng cộng: {total_results_overall}.", level="SUCCESS")
                        else:
                            self.update_log(f"[{city}] Hoàn thành, không tìm thấy kết quả nào.", level="INFO")
                            city_status = "NO_RESULTS"

                    elif city_status == "CAPTCHA_EARLY":
                        self.update_log(f"[{city}] ⚠️ Bị chặn bởi CAPTCHA sớm. Bỏ qua thành phố.", level="CAPTCHA")
                        cities_with_captcha_block += 1
                    elif city_status == "NO_RESULTS":
                        self.update_log(f"[{city}] ℹ️ Không tìm thấy kết quả nào cho tìm kiếm.", level="INFO")
                    elif city_status == "ERROR":
                        if not (f"LỖI: Hàm scrape_city không tồn tại" in self.log_text.get("1.0", tk.END)):
                            self.update_log(f"[{city}] ❌ Gặp lỗi nghiêm trọng. Kiểm tra logs.", level="ERROR")
                        cities_with_errors += 1
                    else:
                        self.update_log(f"[{city}] ❓ Trạng thái không xác định ('{city_status}').", level="WARNING")
                        cities_with_errors += 1

                except Exception as e_city_run:
                    self.update_log(f"!!! LỖI KHÔNG XỬ LÝ ĐƯỢC khi chạy scrape_city cho {city} !!!", level="ERROR")
                    self.update_log(traceback.format_exc(), level="ERROR")
                    cities_with_errors += 1
                    city_status = "ERROR"
                finally:
                    cities_processed += 1
                    city_end_time = time.time()
                    self.update_log(f"=== Hoàn thành {city} trong {city_end_time - city_start_time:.2f} giây (Status: {city_status}) ===", level="CITY_HEADER")

                # Pause between cities if scraping multiple
                if num_cities > 1 and city_index < num_cities - 1:
                    pause_duration = random.uniform(4.0, 8.0)
                    self.update_status(f"Pausing for {pause_duration:.1f}s before next city ({city_index + 2}/{num_cities})...")
                    self.update_log(f"--- Tạm nghỉ {pause_duration:.1f} giây ---", level="INFO")
                    time.sleep(pause_duration)

            # Scraping finished, process results
            self.root.after(0, self.on_scraping_complete, cities_processed, cities_with_errors, cities_with_captcha_block, total_results_overall)

        except Exception as e_thread:
            self.update_log(f"!!! LỖI NGHIÊM TRỌNG TRONG LUỒNG SCRAPING CHÍNH !!!", level="ERROR")
            self.update_log(traceback.format_exc(), level="ERROR")
            self.root.after(0, self.on_scraping_error, f"Critical error in main loop: {e_thread}")

        finally:
            end_time = time.time()
            total_duration = end_time - start_time
            self.update_log(f"\n=== LUỒNG SCRAPING KẾT THÚC SAU {total_duration:.2f} giây ({total_duration/60:.2f} phút) ===", level="INFO")

    def on_scraping_complete(self, cities_processed, cities_with_errors, cities_with_captcha_block, total_results_found):
        """Tasks to run in the main thread after scraping loop finishes."""
        # Stop and hide progress bar
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        self.update_status("Scraping loop complete. Processing and saving results...")
        self.update_log("\n--- Processing and Saving Results ---", level="INFO")
        output_file = self.filename_var.get()
        export_successful = False
        final_save_path = output_file
        saved_format = ""
        actual_saved_count = 0

        if self.all_data:
            final_count = len(self.all_data)
            captcha_skipped_count = sum(1 for item in self.all_data if item.get("Notes") == "CAPTCHA Blocked")
            data_error_count = sum(1 for item in self.all_data if "Error" in item.get("Notes", ""))

            self.update_log(f"Đã xử lý {cities_processed} thành phố.")
            if cities_with_captcha_block > 0: self.update_log(f"   -> {cities_with_captcha_block} thành phố bị chặn bởi CAPTCHA sớm.", level="WARNING")
            if cities_with_errors > 0: self.update_log(f"   -> {cities_with_errors} thành phố gặp lỗi.", level="ERROR")
            self.update_log(f"Tổng cộng thu thập được {total_results_found} mục.")
            if captcha_skipped_count > 0 : self.update_log(f"   -> {captcha_skipped_count} mục bị chặn bởi CAPTCHA trang chi tiết.", level="WARNING")
            if data_error_count > 0: self.update_log(f"   -> {data_error_count} mục gặp lỗi xử lý/trang chi tiết.", level="ERROR")
            actual_valid_count = final_count - captcha_skipped_count - data_error_count
            self.update_log(f"Số mục hợp lệ ước tính để lưu: {actual_valid_count}")
            self.update_log(f"Chuẩn bị xuất {final_count} hàng vào: {output_file}...", level="INFO")

            try:
                df = pd.DataFrame(self.all_data)
                columns_order = [
                    "Thành phố", "Tên công ty", "Địa chỉ", "Số điện thoại", "Website",
                    "Giờ hoạt động", "Google Maps URL", "Vĩ độ", "Kinh độ", "Notes"
                ]
                for col in columns_order:
                    if col not in df.columns:
                        df[col] = ""
                df = df.reindex(columns=columns_order)

                # Data Cleaning
                self.update_log("Cleaning data...", level="INFO")
                error_placeholders = [
                    '', None, 'Lỗi xử lý', 'Chưa lấy', 'Không tìm thấy', 'Lỗi',
                    'Không lấy được địa chỉ', 'Thất bại', 'Lỗi tải trang (Timeout)', 'Lỗi tải trang',
                    'Không lấy được SĐT', 'Không tìm thấy địa chỉ',
                    'Không tìm thấy SĐT', 'Lỗi phân tích URL', 'URL không hợp lệ', 'Không có trang web',
                    'Chưa thử lấy giờ', 'Không tìm thấy thông tin giờ', 'Lỗi Stale lấy text giờ',
                    'Lỗi xử lý giờ (ngoài)', 'Lỗi tọa độ', 'Lỗi xử lý kết quả'
                ]
                cols_to_clean = [col for col in df.columns if col != 'Notes']
                for col in cols_to_clean:
                    if col in df.columns and df[col].dtype == 'object':
                        df[col] = df[col].replace(dict.fromkeys(error_placeholders, 'N/A'))
                        df[col] = df[col].replace(to_replace=r'^CAPTCHA Blocked.*$', value='N/A', regex=True)
                        df[col] = df[col].fillna('N/A')

                string_cols = df.select_dtypes(include=['object']).columns
                for col in string_cols:
                    if col not in ["Giờ hoạt động", "Notes"] and col in df.columns:
                        df[col] = df[col].astype(str).str.strip().replace(r'\s{2,}', ' ', regex=True)
                        df.loc[df[col] == '', col] = 'N/A'

                if "Giờ hoạt động" in df.columns:
                    df["Giờ hoạt động"] = df["Giờ hoạt động"].astype(str).str.replace(r'\n\s*\n', '\n', regex=True).str.strip()
                    df.loc[df["Giờ hoạt động"].str.upper().isin(['N/A', '', 'KHÔNG TÌM THẤY THÔNG TIN GIỜ']), "Giờ hoạt động"] = 'N/A'

                if "Notes" in df.columns:
                    df["Notes"] = df["Notes"].fillna("")

                df_to_save = df
                actual_saved_count = len(df_to_save)
                self.update_log(f"Saving {actual_saved_count} rows.", level="INFO")
                self.update_log("Data cleaning finished.", level="INFO")

                # Save based on extension
                save_attempted = False
                file_ext = os.path.splitext(output_file)[1].lower()

                if file_ext == ".xlsx":
                    try:
                        save_attempted = True
                        df_to_save.to_excel(output_file, index=False, engine='openpyxl')
                        self.update_log(f"\n✅ Đã lưu xong vào Excel '{output_file}'!", level="SUCCESS")
                        export_successful = True
                        final_save_path = output_file
                        saved_format = "Excel"
                    except ImportError:
                        self.update_log("\n❌ LỖI: Cần 'openpyxl'. Chạy: pip install openpyxl", level="ERROR")
                        ttk.dialogs.Messagebox.show_error(
                            "Need 'openpyxl' library. Install with 'pip install openpyxl' or save as CSV.",
                            "Excel Export Error",
                            parent=self.root
                        )
                    except Exception as e_excel:
                        self.update_log(f"\n❌ LỖI khi lưu Excel '{output_file}': {e_excel}", level="ERROR")
                        self.update_log(traceback.format_exc(), level="ERROR")
                        ttk.dialogs.Messagebox.show_error(
                            f"Failed to save Excel:\n{e_excel}",
                            "Excel Export Error",
                            parent=self.root
                        )

                elif file_ext == ".csv":
                    try:
                        save_attempted = True
                        df_to_save.to_csv(output_file, index=False, encoding='utf-8-sig')
                        self.update_log(f"\n✅ Đã lưu xong vào CSV '{output_file}'!", level="SUCCESS")
                        export_successful = True
                        final_save_path = output_file
                        saved_format = "CSV"
                    except Exception as e_csv:
                        self.update_log(f"\n❌ LỖI khi lưu CSV '{output_file}': {e_csv}", level="ERROR")
                        self.update_log(traceback.format_exc(), level="ERROR")
                        ttk.dialogs.Messagebox.show_error(
                            f"Failed to save CSV:\n{e_csv}",
                            "CSV Export Error",
                            parent=self.root
                        )
                
                else:
                    self.update_log(f"\n⚠️ Định dạng không hỗ trợ: '{os.path.basename(output_file)}'. Lưu dạng CSV.", level="WARNING")
                    fallback_csv_path = os.path.splitext(output_file)[0] + ".csv"
                    try:
                        save_attempted = True
                        df_to_save.to_csv(fallback_csv_path, index=False, encoding='utf-8-sig')
                        self.update_log(f"   ✅ Đã lưu dữ liệu vào CSV dự phòng '{fallback_csv_path}'.", level="SUCCESS")
                        export_successful = True
                        final_save_path = fallback_csv_path
                        saved_format = "CSV (Fallback)"
                        ttk.dialogs.messagebox.showwarning("Saved as CSV",
                                               f"Unrecognized extension. Data saved as CSV:\n'{os.path.basename(fallback_csv_path)}'")
                    except Exception as e_csv_fallback:
                        self.update_log(f"   ❌ LỖI khi lưu CSV dự phòng: {e_csv_fallback}", level="ERROR")
                        ttk.dialogs.messagebox.showerror("Fallback Save Error", f"Failed to save fallback CSV:\n{e_csv_fallback}")

                if not save_attempted:
                     self.update_log("\n⚠️ Không thể lưu file.", level="WARNING")

            except Exception as e_df:
                 self.update_log(f"\n❌ LỖI nghiêm trọng khi xử lý dữ liệu/làm sạch: {e_df}", level="ERROR")
                 self.update_log(traceback.format_exc(), level="ERROR")
                 ttk.dialogs.messagebox.showerror("Data Processing Error", f"Error during data processing/cleaning:\n{e_df}")
            # --- End copy ---

        else:
            self.update_log("\n🤷 Không có dữ liệu để lưu.", level="WARNING")
            ttk.dialogs.messagebox.showinfo("No Data", "No data was collected or available to save.")
            export_successful = True # Consider it 'successful' completion

        # --- Finalize GUI state ---
        if export_successful:
            final_msg = f"Complete. Processed {cities_processed} cities."
            if self.all_data and saved_format and actual_saved_count > 0:
                 final_msg += f" {actual_saved_count} rows saved to {os.path.basename(final_save_path)} ({saved_format})."
            elif not self.all_data or actual_saved_count == 0:
                 final_msg += " No data collected/saved."
            else: # Data exists but save failed
                 final_msg += " Failed to save results. Check logs."

            if cities_with_captcha_block > 0: final_msg += f" ({cities_with_captcha_block} cities CAPTCHA blocked)."
            if cities_with_errors > 0: final_msg += f" ({cities_with_errors} cities had errors)."
            self.update_status(final_msg)
        else:
            self.update_status("Scraping complete, but failed to process or save results. Check logs.")

        self.scraping_active = False
        # Re-enable controls safely
        if self.start_button.winfo_exists(): self.start_button.config(state='normal')
        if self.browse_button.winfo_exists(): self.browse_button.config(state='normal')
        if self.filename_entry.winfo_exists(): self.filename_entry.config(state='normal')
        # Re-enable combobox back to 'normal' unless it was initially disabled
        if self.city_combobox.winfo_exists():
             # Only enable if it wasn't disabled due to no config cities initially
             if self.selected_city_var.get() != "No cities configured!":
                  self.city_combobox.config(state='normal') # Set back to normal


    def on_scraping_error(self, error_message):
        """Tasks to run in the main thread if a critical error occurred."""
        # --- This function also remains largely the same ---
        # --- The only change is re-enabling the combobox to 'normal' ---

        self.update_log(f"\n--- SCRAPING HALTED DUE TO CRITICAL ERROR ---", level="ERROR")
        self.update_status(f"Critical Error: {error_message}")
        ttk.dialogs.messagebox.showerror("Scraping Error", f"A critical error stopped the process:\n{error_message}\n\nCheck logs.")
        self.scraping_active = False
        # Ensure controls are re-enabled even on error
        try:
            if self.start_button.winfo_exists(): self.start_button.config(state='normal')
            if self.browse_button.winfo_exists(): self.browse_button.config(state='normal')
            if self.filename_entry.winfo_exists(): self.filename_entry.config(state='normal')
            # Re-enable combobox back to 'normal' unless it was initially disabled
            if self.city_combobox.winfo_exists():
                if self.selected_city_var.get() != "No cities configured!":
                    self.city_combobox.config(state='normal') # Set back to normal
        except tk.TclError:
            pass # Window might be closing

# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ScraperApp(root)
    # Add a check for closing the window gracefully (optional but good practice)
    def on_closing():
        if app.scraping_active:
             if ttk.dialogs.messagebox.askokcancel("Quit", "Scraping is active. Quit anyway?"):
                 # Note: This won't cleanly stop the thread immediately without
                 # more complex thread management (e.g., stop events).
                 # It just closes the GUI.
                 root.destroy()
        else:
             root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()