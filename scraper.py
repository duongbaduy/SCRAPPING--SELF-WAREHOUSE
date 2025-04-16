# gmaps_scraper_project/scraper.py

# -*- coding: utf-8 -*-
import time
import random
import re
import traceback
import os
from urllib.parse import urlparse, parse_qs, urlsplit

# --- Selenium Imports ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException
)

# --- Project Imports ---
from config import USER_AGENT_LIST, MAX_RESULTS_TO_COLLECT_PER_CITY, MAX_RESULTS_TO_PROCESS_PER_CITY, MAX_SCROLL_ATTEMPTS


# --- Helper Function for CAPTCHA Detection ---
def check_for_captcha(driver, log_callback, context=""):
    """Checks for common CAPTCHA elements."""
    captcha_found = False
    captcha_selectors = [
        (By.CSS_SELECTOR, "iframe[src*='recaptcha']"),
        (By.XPATH, "//iframe[contains(@title, 'reCAPTCHA') or contains(@title, 'recaptcha')]"),
        (By.CSS_SELECTOR, "div.g-recaptcha"),
        (By.XPATH, "//div[contains(text(), 'verify that you are not a robot')]"),
        (By.XPATH, "//div[contains(text(), 'Unusual traffic from your computer network')]"),
        (By.ID, "captcha-form") # Another possible CAPTCHA element ID
    ]
    detected_details = ""

    # log_callback(f"[CAPTCHA Check {context}] Checking...") # Can be verbose
    original_timeout = 0
    try:
        # Get current implicit wait to restore later
        original_timeout = driver.timeouts.implicit_wait
    except Exception:
        log_callback(f"[CAPTCHA Check {context}] Warning: Could not get initial implicit wait time.")
        pass # Ignore if error getting initial timeout

    driver.implicitly_wait(0.5) # Reduce implicit wait for faster checking

    try:
        for method, selector in captcha_selectors:
            try:
                elements = driver.find_elements(method, selector)
                visible_elements = []
                for el in elements:
                    try:
                        # Check visibility robustly
                        if el.is_displayed():
                            visible_elements.append(el)
                    except StaleElementReferenceException:
                        # Element disappeared during check, ignore it
                        continue
                    except WebDriverException as e_disp:
                        # Catch other potential errors during display check
                        # log_callback(f"[CAPTCHA Check {context}] Minor error checking display for {selector}: {e_disp}")
                        continue

                if visible_elements:
                    captcha_found = True
                    detected_details = f"Found {len(visible_elements)} visible element(s) matching '{selector}'"
                    log_callback(f"[CAPTCHA Check {context}] !!! CAPTCHA DETECTED !!! ({detected_details})")
                    # Optionally take a screenshot for debugging
                    try:
                         timestamp = time.strftime('%Y%m%d_%H%M%S')
                         screenshot_path = os.path.join(os.getcwd(), f"captcha_detected_{context.replace(' ','_')}_{timestamp}.png")
                         if not os.path.exists(os.path.dirname(screenshot_path)):
                            os.makedirs(os.path.dirname(screenshot_path)) # Ensure directory exists
                         driver.save_screenshot(screenshot_path)
                         log_callback(f"[CAPTCHA Check {context}] Saved screenshot to: {screenshot_path}")
                    except Exception as e_ss:
                         log_callback(f"[CAPTCHA Check {context}] Failed to save screenshot: {e_ss}")
                    break # Stop checking once found
            except WebDriverException as e_find:
                # Ignore certain WebDriver exceptions during the find_elements check itself
                # log_callback(f"[CAPTCHA Check {context}] Minor WebDriver error finding {selector}: {e_find}")
                pass
            except Exception as e_generic:
                 # Log unexpected errors during check
                 log_callback(f"[CAPTCHA Check {context}] Unexpected error checking selector '{selector}': {e_generic}")

    finally:
        # Restore original implicit wait carefully
        if original_timeout is not None:
             try:
                 driver.implicitly_wait(original_timeout)
             except Exception as e_restore_wait:
                  log_callback(f"[CAPTCHA Check {context}] Warning: Failed to restore implicit wait: {e_restore_wait}")

    return captcha_found, detected_details

# --- Main Scraping Function ---
def scrape_city(city, log_callback):
    """Scrapes data for a given city, logs progress via callback, and handles CAPTCHAs."""
    search_query = f"Self Storage {city} Australia"
    log_callback(f"--- Bắt đầu thu thập dữ liệu cho: {city} ---")

    # --- Options ---
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless=new") # Use new headless mode if needed
    selected_user_agent = random.choice(USER_AGENT_LIST) # Use from config
    log_callback(f"[{city}] Using User-Agent: {selected_user_agent}")
    options.add_argument(f"user-agent={selected_user_agent}")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US,en;q=0.9") # Set language preference
    options.add_argument("--disable-blink-features=AutomationControlled") # Try to hide automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"]) # Remove automation bar and logs
    options.add_experimental_option('useAutomationExtension', False)
    # Preferences to potentially reduce detection
    options.add_experimental_option("prefs", {
        "credentials_enable_service": False, # Disable password saving popup
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2 # Disable notifications
    })

    driver = None
    city_data = [] # Initialize data list for this city
    status = "INIT" # Possible statuses: INIT, OK, CAPTCHA_EARLY, NO_RESULTS, ERROR

    try:
        # Khởi tạo WebDriver
        log_callback(f"[{city}] Khởi tạo trình duyệt Chrome...")
        try:
            # Ensure WebDriver Manager downloads the driver if needed
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            status = "DRIVER_OK"
        except Exception as e_wdm:
            log_callback(f"[{city}] LỖI NGHIÊM TRỌNG khi khởi tạo WebDriver: {e_wdm}")
            log_callback(f"[{city}] Chi tiết lỗi:\n{traceback.format_exc()}")
            log_callback(f"[{city}] Kiểm tra kết nối mạng, quyền ghi, hoặc cài đặt Chrome/ChromeDriver.")
            status = "ERROR"
            return [], status # Return empty list and error status if driver fails to start

        log_callback(f"[{city}] Trình duyệt đã khởi tạo.")

        # --- Stealth settings (Execute CDP command) ---
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                      get: () => undefined
                    });
                    Object.defineProperty(navigator, 'languages', {
                      get: () => ['en-US', 'en']
                    });
                    Object.defineProperty(navigator, 'plugins', {
                      get: () => [1, 2, 3, 4, 5], // Mimic some plugins
                    });
                    // Trying to override Permissions API query result for notifications
                    const originalQuery = navigator.permissions.query;
                    navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                    // Remove specific Chrome/WebDriver properties
                    delete navigator.__proto__.webdriver;
                    delete window.chrome;
                    delete window.navigator.brave; // If Brave browser is used

                """
            })
            log_callback(f"[{city}] Áp dụng cài đặt stealth.")
        except Exception as e_cdp:
            log_callback(f"[{city}] Cảnh báo: Không thể thực thi CDP command (có thể do phiên bản trình duyệt/driver): {e_cdp}")

        # --- Navigate and Initial Wait ---
        driver.get("https://www.google.com/maps")
        log_callback(f"[{city}] Đã mở Google Maps.")
        time.sleep(random.uniform(3.0, 5.0)) # Slightly longer initial wait

        # --- CAPTCHA Check 1: After initial load ---
        captcha_present, _ = check_for_captcha(driver, log_callback, "Initial Load")
        if captcha_present:
            log_callback(f"[{city}] CẢNH BÁO NGHIÊM TRỌNG: Phát hiện CAPTCHA ngay khi tải Google Maps. Hủy bỏ thành phố này.")
            try: driver.get("about:blank") # Try navigating away
            except: pass
            status = "CAPTCHA_EARLY"
            return [], status # Stop processing this city

        # --- Handle Consent ---
        try:
            # More robust selector combining different possible button texts/labels
            consent_locator = (By.XPATH, "//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Reject all') or contains(text(), 'I agree') or contains(text(), 'Manage options')]] | //button[contains(@aria-label, 'Accept all') or contains(@aria-label, 'Reject all') or contains(@aria-label, 'Agree') or contains(@aria-label, 'manage') or contains(@aria-label, 'options')] | //form[contains(@action, 'consent')]//button[span]")
            consent_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(consent_locator))
            log_callback(f"[{city}] Tìm thấy nút consent/manage options. Thử nhấp...")
            # Prioritize clicking "Accept all" or "Agree" if multiple buttons match
            possible_texts = ["Accept all", "Agree", "I agree"]
            accepted = False
            try:
                 button_text = consent_button.text.lower()
                 button_label = consent_button.get_attribute('aria-label').lower() if consent_button.get_attribute('aria-label') else ""
                 if any(txt in button_text or txt in button_label for txt in possible_texts):
                      # Try JS click first
                      try:
                         driver.execute_script("arguments[0].click();", consent_button)
                         log_callback(f"[{city}] Đã nhấp nút consent ({consent_button.text}) bằng JS.")
                         accepted = True
                      except Exception as e_js_click:
                         log_callback(f"[{city}] JS click consent thất bại ({e_js_click}), thử ActionChains...")
                         ActionChains(driver).move_to_element(consent_button).pause(random.uniform(0.3, 0.7)).click().perform()
                         log_callback(f"[{city}] Đã nhấp nút consent ({consent_button.text}) bằng ActionChains.")
                         accepted = True
                 else:
                      log_callback(f"[{city}] Nút tìm thấy không phải là Accept/Agree (có thể là Reject/Manage). Không nhấp.")
                      # Decide whether to click Reject/Manage or just proceed
                      # For scraping, often best to proceed without explicit rejection unless needed.

            except ElementClickInterceptedException:
                 log_callback(f"[{city}] Nhấp nút consent bị chặn.")
            except Exception as e_click_consent:
                 log_callback(f"[{city}] Lỗi khi nhấp nút consent: {e_click_consent}")

            if accepted:
                 time.sleep(random.uniform(1.8, 3.2)) # Wait after clicking

        except TimeoutException:
            log_callback(f"[{city}] Không tìm thấy nút consent hoặc không cần thiết.")
        except Exception as e_consent:
            log_callback(f"[{city}] Lỗi khi xử lý consent: {e_consent}")

        # --- Search ---
        try:
            search_box = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "searchboxinput")))
            search_box.clear()
            # Simulate typing more naturally
            log_callback(f"[{city}] Bắt đầu gõ vào ô tìm kiếm...")
            for char in search_query:
                 search_box.send_keys(char)
                 time.sleep(random.uniform(0.06, 0.18))
            search_box.send_keys(Keys.ENTER)
            log_callback(f"[{city}] Đã tìm kiếm: {search_query}")

            # Wait for results area or "no results" message
            results_indicator_xpath = "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]"
            # More robust "No results" detection
            no_results_xpath = "//div[contains(@class, 'fontBodyMedium') and (contains(., 'No results found') or contains(., 'did not match any locations'))] | //div[contains(text(), \"Google Maps can't find\")]"
            first_link_xpath = "//a[contains(@href, '/maps/place/')][@aria-label]"

            WebDriverWait(driver, 25).until( # Longer wait for search results
                 EC.any_of(
                     EC.presence_of_element_located((By.XPATH, results_indicator_xpath)),
                     EC.presence_of_element_located((By.XPATH, no_results_xpath)),
                     EC.presence_of_element_located((By.XPATH, first_link_xpath)) # Sometimes the panel label doesn't show but links do
                 )
            )
            log_callback(f"[{city}] Trang kết quả đã bắt đầu tải (hoặc báo không có kết quả).")
            time.sleep(random.uniform(4, 7)) # Wait longer for results/potential CAPTCHA

            # --- CAPTCHA Check 2: After search results appear (or fail) ---
            captcha_present, _ = check_for_captcha(driver, log_callback, "After Search")
            if captcha_present:
                log_callback(f"[{city}] CẢNH BÁO NGHIÊM TRỌNG: Phát hiện CAPTCHA sau khi tìm kiếm. Hủy bỏ thành phố này.")
                try: driver.get("about:blank")
                except: pass
                status = "CAPTCHA_EARLY" # Treat as early block
                return [], status # Stop processing this city

            # Check if "No results" was found explicitly
            try:
                no_results_elements = driver.find_elements(By.XPATH, no_results_xpath)
                if any(el.is_displayed() for el in no_results_elements):
                    log_callback(f"[{city}] Tìm thấy thông báo 'No results found'. Kết thúc tìm kiếm cho thành phố này.")
                    status = "NO_RESULTS"
                    return [], status # No results, end function for this city
            except NoSuchElementException:
                log_callback(f"[{city}] Không thấy thông báo 'No results found', tiếp tục xử lý.")
                pass # Results likely present or other state
            except Exception as e_no_res_check:
                 log_callback(f"[{city}] Lỗi nhỏ khi kiểm tra 'No results': {e_no_res_check}")


        except TimeoutException as e_search_timeout:
            log_callback(f"[{city}] Lỗi Timeout khi chờ kết quả tìm kiếm xuất hiện (sau 25s).")
            log_callback(traceback.format_exc())
            captcha_present, _ = check_for_captcha(driver, log_callback, "After Search Timeout")
            if captcha_present:
                 log_callback(f"[{city}] Ghi chú: CAPTCHA cũng được phát hiện sau lỗi timeout tìm kiếm. Hủy bỏ thành phố.")
                 status = "CAPTCHA_EARLY"
                 return [], status
            else:
                 status = "ERROR"
                 return [], status # Critical error, stop city
        except Exception as e_search:
            log_callback(f"[{city}] Lỗi nghiêm trọng khi thực hiện tìm kiếm: {e_search}")
            log_callback(traceback.format_exc())
            captcha_present, _ = check_for_captcha(driver, log_callback, "After Search Failure")
            if captcha_present:
                 log_callback(f"[{city}] Ghi chú: CAPTCHA cũng được phát hiện sau lỗi tìm kiếm. Hủy bỏ thành phố.")
                 status = "CAPTCHA_EARLY"
                 return [], status
            else:
                 status = "ERROR"
                 return [], status # Critical error, stop city


        # --- Scroll ---
        scroll_attempts = 0
        # Use config for max scrolls
        max_scroll_attempts = MAX_SCROLL_ATTEMPTS
        # Updated selector for the scrollable feed
        feed_scroll_selector = "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]/parent::div | //div[contains(@class, 'm6QErb')][@role='feed']" # Added alternative class
        try:
            feed_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, feed_scroll_selector))
            )
            log_callback(f"[{city}] Bắt đầu scroll panel kết quả...")
            last_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
            no_change_count = 0
            # Updated end of list detection (more robust)
            end_of_list_xpath = "//span[contains(text(), \"You've reached the end of the list.\")] | //p[contains(., \"You've reached the end of the list.\")] | //span[contains(text(), \"Keine weiteren Ergebnisse\") or contains(text(), \"Aucun autre résultat\")] | //div[contains(@class, 'PbZDve')]//p[contains(@class,'fontBodyMedium')]" # Added generic end-of-list container class

            while scroll_attempts < max_scroll_attempts:
                is_end_visible = False
                try:
                     end_elements = driver.find_elements(By.XPATH, end_of_list_xpath)
                     is_end_visible = any(el.is_displayed() for el in end_elements)
                     if is_end_visible:
                         log_callback(f"[{city}] Phát hiện thông báo cuối danh sách. Dừng scroll.")
                         break
                except (NoSuchElementException, StaleElementReferenceException): pass # Ignore if end element goes stale/not found during check

                # Scroll down using JS
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed_element)
                log_callback(f"[{city}] Đã scroll lần {scroll_attempts + 1}/{max_scroll_attempts}...")
                time.sleep(random.uniform(2.5, 4.5)) # Slightly longer pause between scrolls

                # Check height change reliably
                new_height = last_height # Default to last height in case of error
                try:
                    # Ensure the element is still attached before getting scrollHeight
                    if feed_element.is_enabled(): # Check if still interactable
                        new_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
                    else:
                         log_callback(f"[{city}] Element scroll không còn enabled, thử tìm lại...")
                         raise StaleElementReferenceException("Feed element detached")

                except StaleElementReferenceException:
                    log_callback(f"[{city}] Element scroll bị stale, thử tìm lại...")
                    try:
                        feed_element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, feed_scroll_selector))
                        )
                        new_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
                        log_callback(f"[{city}] Tìm lại element scroll thành công.")
                        no_change_count = 0 # Reset counter after re-find
                    except Exception as e_refind:
                         log_callback(f"[{city}] Tìm lại element scroll cũng lỗi ({e_refind}). Dừng scroll.")
                         break # Stop scrolling if element cannot be reliably found
                except Exception as e_scroll_height:
                     log_callback(f"[{city}] Lỗi không xác định khi lấy scrollHeight: {e_scroll_height}")
                     # Maybe try finding again as above
                     try:
                         feed_element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, feed_scroll_selector)))
                         new_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
                         log_callback(f"[{city}] Tìm lại element scroll thành công (sau lỗi khác).")
                         no_change_count = 0
                     except Exception:
                         log_callback(f"[{city}] Tìm lại element scroll thất bại (sau lỗi khác). Dừng scroll.")
                         break


                if new_height == last_height:
                    no_change_count += 1
                    log_callback(f"[{city}] Chiều cao không đổi (lần {no_change_count}). Kiểm tra lại cuối danh sách...")
                    # Re-check for end message after height stabilized
                    try:
                         end_elements = driver.find_elements(By.XPATH, end_of_list_xpath)
                         is_end_visible = any(el.is_displayed() for el in end_elements)
                         if is_end_visible:
                             log_callback(f"[{city}] Chiều cao không đổi VÀ thấy thông báo cuối danh sách. Dừng scroll.")
                             break
                    except (NoSuchElementException, StaleElementReferenceException): pass

                    if no_change_count >= 3: # Stop after 3 consecutive height stalls
                        log_callback(f"[{city}] Chiều cao không đổi {no_change_count} lần liên tiếp. Dừng scroll.")
                        break
                else:
                    no_change_count = 0 # Reset counter if height changes
                    last_height = new_height

                scroll_attempts += 1
                # Add a small random chance to pause longer during scroll
                if random.random() < 0.15: # Increased chance slightly
                    extra_pause = random.uniform(2.5, 5.0)
                    log_callback(f"[{city}] Tạm dừng scroll thêm {extra_pause:.1f}s...")
                    time.sleep(extra_pause)


            if scroll_attempts == max_scroll_attempts:
                 log_callback(f"[{city}] Đạt số lần scroll tối đa ({max_scroll_attempts}).")

        except TimeoutException:
            log_callback(f"[{city}] Không tìm thấy panel kết quả để scroll ({feed_scroll_selector}). Có thể không có kết quả hoặc lỗi layout.")
        except Exception as e_scroll:
             log_callback(f"[{city}] Lỗi trong quá trình scroll: {e_scroll}")
             log_callback(traceback.format_exc())

        # --- Get Result Links ---
        # Improved XPath for more reliable link extraction
        results_xpath = "//div[contains(@class, 'Nv2PK') or contains(@class, 'THOPZb')]/a[@aria-label and contains(@href, '/maps/place/')]" # Classes often used for result containers
        result_links = []
        processed_links = set() # Keep track of URLs to avoid duplicates
        # Use config limit
        max_results_to_collect = MAX_RESULTS_TO_COLLECT_PER_CITY
        try:
            # Wait briefly for links to be present after scrolling finishes
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, results_xpath)))
            potential_results = driver.find_elements(By.XPATH, results_xpath)
            log_callback(f"[{city}] Tìm thấy {len(potential_results)} thẻ 'a' kết quả tiềm năng sau scroll.")

            collected_count = 0
            for res_element in potential_results:
                 try:
                     # Check if element is still valid and visible
                     if not res_element.is_displayed():
                         continue # Skip hidden elements

                     href = res_element.get_attribute('href')
                     aria_label = res_element.get_attribute('aria-label')

                     # Basic validation and duplicate check
                     if href and href.startswith("https://www.google.com/maps/place/") and aria_label:
                         # Normalize URL slightly (remove trailing slash if exists) for comparison
                         normalized_href = href.rstrip('/')
                         if normalized_href not in processed_links:
                             result_links.append({'href': href, 'aria_label': aria_label})
                             processed_links.add(normalized_href)
                             collected_count += 1
                             if collected_count >= max_results_to_collect:
                                 log_callback(f"[{city}] Đã thu thập đủ {max_results_to_collect} link.")
                                 break
                 except StaleElementReferenceException:
                     log_callback(f"[{city}] Bỏ qua phần tử link bị stale khi lấy href/label.")
                     continue
                 except Exception as e_link_attr:
                     log_callback(f"[{city}] Lỗi nhỏ khi lấy thuộc tính link: {e_link_attr}")
                     continue

            log_callback(f"[{city}] Thu thập được {len(result_links)} link kết quả hợp lệ và duy nhất.")

        except TimeoutException:
             log_callback(f"[{city}] Không tìm thấy link kết quả nào ({results_xpath}) sau khi scroll/chờ.")
        except Exception as e_links:
            log_callback(f"[{city}] Lỗi khi thu thập link kết quả: {e_links}")
            log_callback(traceback.format_exc())

        # --- Process Each Result ---
        if not result_links:
             log_callback(f"[{city}] Không có link kết quả nào để xử lý.")
             if status == "DRIVER_OK": status = "NO_RESULTS" # Update status if no links found after successful start

        # Use config limit
        max_results_to_process = MAX_RESULTS_TO_PROCESS_PER_CITY

        for i, res_info in enumerate(result_links):
            if i >= max_results_to_process:
                log_callback(f"[{city}] Đã đạt giới hạn xử lý {max_results_to_process} kết quả.")
                break

            log_callback(f"\n[{city}] === Đang xử lý Kết quả {i + 1}/{min(len(result_links), max_results_to_process)} ===")
            original_gmaps_url = res_info.get('href', 'Lỗi lấy URL')
            aria_name = res_info.get('aria_label', 'N/A') # Name from the link list
            log_callback(f"[{city}] Tên (từ link): {aria_name}")
            log_callback(f"[{city}] URL Gmaps gốc: {original_gmaps_url}")

            # Initialize data fields for each iteration
            name = aria_name # Start with the name from the link
            address = "Chưa lấy"
            phone_number = "Chưa lấy"
            website_url_full = "Chưa lấy"
            domain_name = "Chưa lấy"
            opening_hours = "Chưa lấy"
            lat, lng = "", ""
            captcha_skipped = False # Flag for this item
            item_error = False # Flag if non-captcha critical error occurs

            try:
                # Navigate to Detail Page
                log_callback(f"[{city}] Đang điều hướng tới: {original_gmaps_url}")
                driver.get(original_gmaps_url)
                detail_page_url = "" # Reset for each item

                # Wait for page elements or CAPTCHA
                try:
                     # Wait for the main business name H1 as primary indicator
                     detail_main_element_xpath = "//h1[contains(@class,'fontHeadlineLarge')]" # More specific H1 often used
                     WebDriverWait(driver, 20).until( # Increased wait for detail page
                         EC.any_of(
                             EC.visibility_of_element_located((By.XPATH, detail_main_element_xpath)),
                             # Fallbacks if H1 structure changes
                             EC.visibility_of_element_located((By.TAG_NAME, "h1")),
                             EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']")),
                             # Also check for CAPTCHA elements as a possible state
                             EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha']")),
                             EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'verify that you are not a robot')]"))
                         )
                     )
                     log_callback(f"[{city}] Trang chi tiết Gmaps đã tải (hoặc có yếu tố CAPTCHA).")
                     time.sleep(random.uniform(3.5, 6.5)) # Wait slightly longer for dynamic content
                     detail_page_url = driver.current_url
                     log_callback(f"[{city}] URL hiện tại sau khi tải: {detail_page_url}")

                     # --- CAPTCHA Check 3: After loading detail page ---
                     captcha_present, captcha_details = check_for_captcha(driver, log_callback, f"Detail Page {i+1} ({aria_name[:30]}...)")
                     if captcha_present:
                         log_callback(f"[{city}] !!! BỎ QUA KẾT QUẢ {i+1} do phát hiện CAPTCHA trên trang chi tiết. !!!")
                         captcha_skipped = True
                         # Set fields to indicate CAPTCHA block
                         address = f"CAPTCHA Blocked ({captcha_details})"
                         phone_number = "CAPTCHA Blocked"; website_url_full = "CAPTCHA Blocked"; domain_name = "CAPTCHA Blocked"; opening_hours = "CAPTCHA Blocked"; lat, lng = "CAPTCHA Blocked", "CAPTCHA Blocked"
                         # Go directly to appending data below (handled by if not captcha_skipped)

                except TimeoutException:
                     log_callback(f"[{city}] CẢNH BÁO: Trang chi tiết Gmaps tải chậm hoặc không có H1/main content/CAPTCHA trong 20s.")
                     detail_page_url = driver.current_url # Get URL even on timeout
                     log_callback(f"[{city}] URL hiện tại (sau timeout): {detail_page_url}")
                     # Still check for CAPTCHA even after timeout
                     captcha_present, captcha_details = check_for_captcha(driver, log_callback, f"Detail Page Timeout {i+1} ({aria_name[:30]}...)")
                     if captcha_present:
                        log_callback(f"[{city}] !!! BỎ QUA KẾT QUẢ {i+1} do phát hiện CAPTCHA sau timeout tải trang chi tiết. !!!")
                        captcha_skipped = True
                        address = f"CAPTCHA Blocked ({captcha_details})"
                        phone_number = "CAPTCHA Blocked"; website_url_full = "CAPTCHA Blocked"; domain_name = "CAPTCHA Blocked"; opening_hours = "CAPTCHA Blocked"; lat, lng = "CAPTCHA Blocked", "CAPTCHA Blocked"
                     else:
                         # If no CAPTCHA and timed out, treat as data extraction failure
                         log_callback(f"[{city}] Lỗi tải trang chi tiết (Timeout), không thể trích xuất dữ liệu.")
                         item_error = True # Mark item as having an error
                         address = "Lỗi tải trang (Timeout)"
                         phone_number = "Lỗi tải trang"; website_url_full = "Lỗi tải trang"; domain_name = "Lỗi tải trang"; opening_hours = "Lỗi tải trang"; lat, lng = "Lỗi tải trang", "Lỗi tải trang"
                         # Skip normal data extraction (handled by if not captcha_skipped and not item_error)

                # --- Extract Data (only if not skipped by CAPTCHA or item error) ---
                if not captcha_skipped and not item_error:
                    # --- Extract Lat/Lng ---
                    # (Keep the existing robust Lat/Lng extraction logic)
                    lat, lng = "", ""
                    coords_found = False
                    try:
                        # Priority: Use current URL after load, fallback to original URL
                        url_to_check_primary = detail_page_url if detail_page_url else original_gmaps_url
                        log_callback(f"[{city}] Checking coords in URL: {url_to_check_primary}")

                        # Regex for @lat,lng format
                        url_pattern = re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+)')
                        coords_match = url_pattern.search(url_to_check_primary)
                        if coords_match:
                            lat, lng = coords_match.group(1), coords_match.group(2)
                            log_callback(f"[{city}] Extracted coords from URL (@): Lat {lat}, Lng {lng}")
                            coords_found = True
                        else:
                            # Regex for data=!3d[...]!4d[...] format
                            data_pattern = re.compile(r'data=.*?(!3d|%213d)(-?\d+\.\d+).*?(!4d|%214d)(-?\d+\.\d+)')
                            data_match = data_pattern.search(url_to_check_primary)
                            if data_match:
                                lat, lng = data_match.group(2), data_match.group(4)
                                log_callback(f"[{city}] Extracted coords from URL (data=): Lat {lat}, Lng {lng}")
                                coords_found = True

                        # Fallback to original URL if not found in current and URLs differ
                        if not coords_found and detail_page_url and original_gmaps_url != detail_page_url:
                            log_callback(f"[{city}] Not found in current URL, trying original: {original_gmaps_url}")
                            coords_match = url_pattern.search(original_gmaps_url)
                            if coords_match:
                                lat, lng = coords_match.group(1), coords_match.group(2)
                                log_callback(f"[{city}] Extracted coords from ORIGINAL URL (@): Lat {lat}, Lng {lng}")
                                coords_found = True
                            else:
                                data_match = data_pattern.search(original_gmaps_url)
                                if data_match:
                                    lat, lng = data_match.group(2), data_match.group(4)
                                    log_callback(f"[{city}] Extracted coords from ORIGINAL URL (data=): Lat {lat}, Lng {lng}")
                                    coords_found = True

                        # Fallback to page source (JS) if still not found
                        if not coords_found:
                             log_callback(f"[{city}] No coords in URLs, trying JS fallback...")
                             try:
                                time.sleep(1) # Short wait before JS execution
                                location_script = """
                                    // Try OG Image meta tag
                                    var ogLoc = document.querySelector('meta[property="og:image"]');
                                    if (ogLoc) { var imgSrc = ogLoc.getAttribute('content'); var match = imgSrc.match(/center=([^&]+)/); if (match && match[1].includes(',')) return match[1]; }
                                    // Try LD+JSON scripts
                                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                    for (const script of scripts) { try { const data = JSON.parse(script.textContent); if (data && data.geo && data.geo.latitude && data.geo.longitude) { return data.geo.latitude + ',' + data.geo.longitude; } } catch (e) {} }
                                    // Try meta itemprops
                                    var latMeta = document.querySelector('meta[itemprop="latitude"]');
                                    var lonMeta = document.querySelector('meta[itemprop="longitude"]');
                                    if(latMeta && lonMeta) { return latMeta.getAttribute('content') + ',' + lonMeta.getAttribute('content');}
                                    return null;"""
                                center_param = driver.execute_script(location_script)
                                if center_param and ',' in center_param:
                                    coords = center_param.split(',')
                                    if len(coords) >= 2:
                                        lat_cand, lng_cand = coords[0].strip(), coords[1].strip()
                                        # Validate format
                                        if re.match(r'^-?\d+(\.\d+)?$', lat_cand) and re.match(r'^-?\d+(\.\d+)?$', lng_cand):
                                            lat, lng = lat_cand, lng_cand
                                            log_callback(f"[{city}] Extracted coords from page source (JS fallback): Lat {lat}, Lng {lng}")
                                            coords_found = True
                                        else: log_callback(f"[{city}] Invalid JS fallback format: {center_param}")
                                    else: log_callback(f"[{city}] Cannot parse coords from JS fallback: {center_param}")
                                else: log_callback(f"[{city}] No coords found via JS fallback (meta/script/itemprop).")
                             except Exception as e_coords_js: log_callback(f"[{city}] Error getting coords via JS fallback: {e_coords_js}")

                        if not coords_found:
                            log_callback(f"[{city}] CẢNH BÁO: Không thể trích xuất tọa độ.")
                            lat, lng = "Không tìm thấy", "Không tìm thấy"

                    except Exception as e_coords:
                        lat, lng = "Lỗi tọa độ", "Lỗi tọa độ"
                        log_callback(f"[{city}] General error extracting coordinates: {e_coords}")

                    # --- Get Name (from H1) ---
                    try:
                        # Use the specific H1 selector identified earlier
                        name_element = WebDriverWait(driver, 8).until(EC.visibility_of_element_located((By.XPATH, detail_main_element_xpath)))
                        fetched_name = name_element.text.strip()
                        if fetched_name:
                            name = fetched_name # Update name if H1 is found and not empty
                            log_callback(f"[{city}] Tên (H1): {name}")
                        else:
                            log_callback(f"[{city}] H1 tìm thấy nhưng trống. Giữ tên từ link: {name}")
                    except TimeoutException:
                        log_callback(f"[{city}] Không tìm thấy H1 chính trong 8s. Thử H1 chung...")
                        try: # Fallback to generic H1
                             name_element = WebDriverWait(driver, 2).until(EC.visibility_of_element_located((By.TAG_NAME, "h1")))
                             fetched_name = name_element.text.strip()
                             if fetched_name: name = fetched_name; log_callback(f"[{city}] Tên (H1 fallback): {name}")
                             else: log_callback(f"[{city}] H1 fallback trống. Giữ tên từ link: {name}")
                        except Exception: log_callback(f"[{city}] H1 fallback cũng không tìm thấy. Giữ tên từ link: {name}")
                    except (NoSuchElementException, StaleElementReferenceException):
                        log_callback(f"[{city}] H1 bị stale/không tìm thấy khi lấy tên. Giữ tên từ link: {name}")
                    except Exception as e_name: log_callback(f"[{city}] Lỗi khi lấy tên từ H1: {e_name}.")

                    # --- Get Address ---
                    # (Keep existing robust address extraction)
                    address = "Không lấy được địa chỉ"
                    address_source = "N/A"
                    address_found = False
                    address_selectors = [
                        (By.CSS_SELECTOR, "button[data-item-id='address']"),             # Preferred button
                        (By.CSS_SELECTOR, "a[data-item-id='address']"),                 # Sometimes it's a link
                        (By.XPATH, "//button[contains(@aria-label, 'Address:')]"),       # Button with aria-label
                        (By.XPATH, "//a[contains(@aria-label, 'Address:')]"),           # Link with aria-label
                        (By.XPATH, "//div[contains(@class, 'Io6YTe') and .//img[contains(@src,'ic_pin_place')]]"), # Text near pin icon
                        (By.XPATH, "//div[contains(@class, 'rogA2c')]/div[contains(@class, 'Io6YTe')]"), # Common structure with inner text div
                        (By.XPATH, "//button[@data-tooltip='Copy address']/following-sibling::div[1]"), # Div after copy button
                        (By.XPATH, "//div[@data-tooltip='Copy address']//following-sibling::div[contains(@class,'Io6YTe')]") # Text after copy tooltip (fallback)
                    ]

                    for method, selector in address_selectors:
                        if address_found: break
                        try:
                            addr_elements = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((method, selector)))
                            for element in addr_elements:
                                try:
                                    if not element.is_displayed(): continue

                                    addr_text = ""
                                    # Try getting text from specific inner divs first
                                    try:
                                        inner_text_el = element.find_element(By.CSS_SELECTOR, "div.Io6YTe, div.QsDR1c")
                                        addr_text = inner_text_el.text.strip()
                                    except NoSuchElementException:
                                        pass # Fallback to element's text or aria-label

                                    # If inner text empty, try element's text
                                    if not addr_text:
                                        addr_text = element.text.strip()

                                    # If still empty, try aria-label
                                    if not addr_text:
                                        aria_label = element.get_attribute('aria-label')
                                        if aria_label and ('Address:' in aria_label or 'Địa chỉ:' in aria_label):
                                            addr_text = re.sub(r'(Address:|Địa chỉ:)\s*', '', aria_label).strip()


                                    # Validate and assign
                                    if addr_text and len(addr_text) > 5: # Basic validation
                                        address = addr_text
                                        address_source = f"Selector: {selector}"
                                        address_found = True
                                        break # Found address with this selector
                                except StaleElementReferenceException: continue # Element went stale, try next element/selector
                        except TimeoutException: continue # Selector not found within timeout
                        except StaleElementReferenceException: log_callback(f"[{city}] Address selector itself stale {selector}"); continue
                        except Exception as e_addr_sel: log_callback(f"[{city}] Minor error checking address {selector}: {e_addr_sel}"); continue

                    if not address_found: address = "Không tìm thấy địa chỉ" # More specific than 'không lấy được'
                    log_callback(f"[{city}] Địa chỉ ({'Tìm thấy' if address_found else 'Không tìm thấy'}): {address}")

                    # --- Get Phone Number ---
                    # (Keep existing robust phone extraction)
                    phone_number = "Không tìm thấy SĐT"
                    phone_selectors = [
                        (By.CSS_SELECTOR, "button[data-item-id^='phone:tel:']"), # Preferred button
                        (By.CSS_SELECTOR, "a[data-item-id^='phone:tel:']"),     # Preferred link
                        (By.XPATH, "//button[contains(@aria-label, 'Phone:')]"),   # Button by aria-label
                        (By.XPATH, "//a[contains(@aria-label, 'Phone:')]"),       # Link by aria-label
                        (By.XPATH, "//div[contains(@class, 'rogA2c') and .//span[contains(text(),'call')]]//div[contains(@class, 'Io6YTe')]"), # Text near call icon
                        (By.XPATH, "//button[@data-tooltip='Copy phone number']/following-sibling::div[1]"), # Div after copy button
                        (By.XPATH, "//div[@data-tooltip='Copy phone number']//following-sibling::div[contains(@class,'Io6YTe')]"), # Text after copy tooltip
                        (By.CSS_SELECTOR, "a[href^='tel:']") # Generic tel: link fallback
                    ]
                    phone_found = False

                    for method, selector in phone_selectors:
                        if phone_found: break
                        try:
                             elements = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((method, selector)))
                             for element in elements:
                                 try:
                                     if not element.is_displayed(): continue

                                     pn_text = ""
                                     # 1. Try inner text (Io6YTe or QsDR1c often hold the text)
                                     try:
                                         inner_text_el = element.find_element(By.CSS_SELECTOR, "div.Io6YTe, div.QsDR1c")
                                         pn_text = inner_text_el.text.strip()
                                         if pn_text and re.search(r'[\d\+() -]{7,}', pn_text): phone_found = True; break
                                     except NoSuchElementException: pass

                                     # 2. Try element's text if inner failed
                                     if not phone_found:
                                         pn_text = element.text.strip()
                                         if pn_text and re.search(r'[\d\+() -]{7,}', pn_text): phone_found = True; break

                                     # 3. Try href attribute (for tel: links)
                                     if not phone_found and element.tag_name == 'a':
                                         href = element.get_attribute('href')
                                         if href and href.startswith('tel:'):
                                             pn_text = href.replace('tel:', '').strip()
                                             # Clean common non-numeric chars often left in tel: links
                                             pn_text = re.sub(r'[^\d\+\(\)\s-]', '', pn_text)
                                             if pn_text and re.search(r'[\d\+() -]{7,}', pn_text): phone_found = True; break

                                     # 4. Try aria-label
                                     if not phone_found:
                                         aria_label = element.get_attribute('aria-label')
                                         if aria_label:
                                             # Extract num from label (more robust regex)
                                             match = re.search(r'(?:Phone|Điện thoại):\s*([\+\d\s\(\)-]+)', aria_label, re.IGNORECASE)
                                             if match:
                                                 pn_text = match.group(1).strip()
                                                 if pn_text and re.search(r'[\d\+() -]{7,}', pn_text): phone_found = True; break
                                 except StaleElementReferenceException: continue # Element stale, try next

                             if phone_found:
                                 phone_number = pn_text
                                 log_callback(f"[{city}] SĐT ({selector}): {phone_number}")
                                 break # Exit outer loop once found

                        except TimeoutException: continue
                        except StaleElementReferenceException: log_callback(f"[{city}] Phone selector itself stale {selector}"); continue
                        except Exception as e_phone_sel: log_callback(f"[{city}] Minor error checking phone {selector}: {e_phone_sel}"); continue

                    if not phone_found: phone_number = "Không tìm thấy SĐT"


                    # --- Get Website URL ---
                    # (Keep existing robust website extraction)
                    website_url_full = "Không có trang web"
                    domain_name = "Không có trang web"
                    website_found = False
                    website_selectors = [
                        (By.CSS_SELECTOR, "a[data-item-id='authority']"), # Official Website Link
                        (By.XPATH, "//a[contains(@aria-label, 'Website:')]"), # Link by aria-label
                        (By.XPATH, "//button[contains(@aria-label, 'Website:')]"), # Button by aria-label (less common for link)
                        (By.XPATH, "//div[contains(@class, 'rogA2c') and .//span[contains(text(),'public')]]//div[contains(@class, 'Io6YTe')]//a"), # Link near globe icon
                        (By.XPATH, "//a[@data-tooltip='Open website in new tab']"), # Tooltip based link
                        (By.XPATH, "//div[@data-tooltip='Open website']//following-sibling::div//a"), # Link near tooltip (fallback)
                    ]

                    for method, selector in website_selectors:
                         if website_found: break
                         try:
                             elements = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((method, selector)))
                             for element in elements:
                                 try:
                                     if not element.is_displayed(): continue

                                     href = element.get_attribute('href')
                                     if href and href.startswith('http'):
                                         website_url_full = href
                                         website_found = True
                                         log_callback(f"[{city}] Tìm thấy URL ({selector}): {website_url_full}")
                                         break # Found one
                                 except StaleElementReferenceException: continue # Element stale

                             if website_found: break # Exit outer loop
                         except TimeoutException: continue
                         except StaleElementReferenceException: log_callback(f"[{city}] Website selector itself stale {selector}"); continue
                         except Exception as e_web_sel: log_callback(f"[{city}] Minor error checking website {selector}: {e_web_sel}"); continue

                    if website_found:
                         # Handle Google redirect links
                         if '/url?q=' in website_url_full:
                              try:
                                   parsed_url = urlsplit(website_url_full)
                                   query_params = parse_qs(parsed_url.query)
                                   extracted_url = query_params.get('q', [None])[0]
                                   if extracted_url and extracted_url.startswith('http'):
                                       website_url_full = extracted_url
                                       log_callback(f"[{city}] Trích xuất URL thực từ Google redirect: {website_url_full}")
                                   else: log_callback(f"[{city}] Giữ lại URL redirect (không trích xuất được q hoặc URL không hợp lệ).")
                              except Exception as e_redirect:
                                   log_callback(f"[{city}] Lỗi khi xử lý Google redirect URL: {e_redirect}")

                         # Extract domain
                         if website_url_full and website_url_full.startswith('http'):
                             try:
                                 parsed_uri = urlparse(website_url_full)
                                 netloc = parsed_uri.netloc.lower()
                                 # Remove www. if present
                                 domain_name = netloc[4:] if netloc.startswith('www.') else netloc
                                 domain_name = domain_name.rstrip('/')
                                 # Handle cases like example.com.au or example.co.uk
                                 domain_parts = domain_name.split('.')
                                 if len(domain_parts) > 2 and len(domain_parts[-1]) <= 3 and len(domain_parts[-2]) <= 3:
                                      # Likely a complex TLD like .com.au, keep last 3 parts
                                      domain_name = ".".join(domain_parts[-3:])
                                 elif len(domain_parts) > 2:
                                      # Standard domain like www.sub.example.com -> example.com
                                      domain_name = ".".join(domain_parts[-2:])

                                 log_callback(f"[{city}] Trích xuất tên miền: {domain_name}")
                             except Exception as e_parse:
                                 log_callback(f"[{city}] Lỗi khi phân tích URL trang web thành tên miền: {e_parse}")
                                 domain_name = "Lỗi phân tích URL"
                         else: domain_name = "URL không hợp lệ"
                    else:
                         log_callback(f"[{city}] Không tìm thấy link trang web.")
                         website_url_full = "Không có trang web"; domain_name = "Không có trang web"


                    # --- Get Opening Hours ---
                    # (Keep existing robust opening hours logic)
                    opening_hours = "Không tìm thấy thông tin giờ" # Default if nothing found
                    hours_found = False
                    try:
                        # Strategy:
                        # 1. Look for the visible hours summary first (e.g., "Open ⋅ Closes 5 PM")
                        # 2. If summary found, try clicking the hours trigger (button/div)
                        # 3. If clicked, wait for the detailed hours table/panel to appear
                        # 4. Extract text from the detailed panel/table
                        # 5. If click/panel fails, use the initial summary or aria-label as fallback.

                        hours_summary_element = None
                        hours_trigger_element = None
                        hours_panel_element = None
                        clicked = False
                        hours_summary_text = ""

                        # Selectors (Combine and prioritize)
                        # Trigger first (often needed to reveal details)
                        hours_trigger_selectors = [
                            # Buttons/Divs clearly indicating hours, preferring those NOT saying "Hide" / "Collapse"
                            (By.XPATH, "(//button[contains(@aria-label, 'Hour') and not(contains(@aria-label, 'Hide')) and not(contains(@aria-label, 'Collapse'))] | //div[@role='button' and contains(@aria-label, 'Hour') and not(contains(@aria-label, 'Hide')) and not(contains(@aria-label, 'Collapse'))])[1]"),
                            (By.CSS_SELECTOR, "button[data-item-id^='oh']"), # Common data-item-id
                            (By.XPATH, "//button[contains(@class, 'AeaXub')]"), # Common class
                            (By.XPATH, "//div[contains(@class, 'AeaXub')][@role='button']"), # Common class + role
                            (By.XPATH, "//div[contains(@class,'GMBkld')]//span[contains(@class, ' 接客時間')]/ancestor::button"), # Japanese example structure
                            (By.CSS_SELECTOR, "div.OMl5r[role='button']"), # Another common div role
                            # Div containing clock icon (often clickable)
                            (By.XPATH, "//div[.//span[contains(@class, 'google-symbols') and (contains(text(),'schedule') or contains(text(),'access_time'))]][@role='button']") # include access_time icon
                        ]
                        # Summary text (often visible without click)
                        hours_summary_xpath = "//div[contains(@class,'Io6YTe')]//span[contains(., 'Open') or contains(., 'Closed') or contains(., 'Opens') or contains(., 'Closes')] | //span[@class='ZDu9vd' or contains(@class,'state')]" # Add common state spans

                        # Panel/Table (appears after click)
                        hours_panel_selectors = [
                            (By.XPATH, "//table[contains(@class, 'eK4R0e')] | //table[contains(@class, 'WgFkxc')]"), # Preferred table classes
                            (By.XPATH, "//div[contains(@class, 't39EBf')]//table"),
                            (By.XPATH, "//table[contains(@aria-label, 'Opening hours')] | //table[contains(@aria-label, 'Giờ mở cửa')]"),
                            (By.XPATH, "//div[contains(@class, 'm6QErb')]//table"), # Common container
                            (By.XPATH, "//div[contains(@class, 'm6QErb')]"), # Fallback to container div itself
                        ]


                        # 1a. Try finding the summary text directly first
                        try:
                             summary_elements = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((By.XPATH, hours_summary_xpath)))
                             visible_summaries = [el.text.strip() for el in summary_elements if el.is_displayed()]
                             if visible_summaries:
                                 hours_summary_text = visible_summaries[0] # Take the first visible one
                                 if hours_summary_text:
                                     opening_hours = hours_summary_text # Initial fallback
                                     log_callback(f"[{city}] Found hours summary: {opening_hours}")
                        except TimeoutException:
                             log_callback(f"[{city}] No simple hours summary found initially.")
                        except Exception as e_sum:
                            log_callback(f"[{city}] Error getting initial hours summary: {e_sum}")


                        # 1b. Now, find the clickable trigger element
                        log_callback(f"[{city}] Looking for hours trigger element to click...")
                        for method, selector in hours_trigger_selectors:
                            try:
                                # Find potentially multiple triggers, prioritize clickable ones
                                triggers = WebDriverWait(driver, 1).until(EC.presence_of_all_elements_located((method, selector)))
                                clickable_triggers = [t for t in triggers if t.is_displayed() and t.is_enabled()]
                                if clickable_triggers:
                                    hours_trigger_element = clickable_triggers[0] # Take the first visible/enabled one
                                    log_callback(f"[{city}] Found hours trigger (Selector: {selector})")
                                    break
                            except TimeoutException: continue
                            except StaleElementReferenceException: continue
                            except Exception: continue # Ignore other errors finding trigger

                        # 2. Click the trigger if found
                        if hours_trigger_element:
                            log_callback(f"[{city}] Attempting to click hours trigger...")
                            try:
                                # Move mouse slightly before clicking
                                ActionChains(driver).move_to_element(hours_trigger_element).pause(random.uniform(0.2, 0.5)).perform()
                                # Try JS click first (often bypasses overlays)
                                driver.execute_script("arguments[0].click();", hours_trigger_element)
                                log_callback(f"[{city}] Clicked hours trigger (JS).")
                                clicked = True
                                time.sleep(random.uniform(1.8, 2.8)) # Wait for panel to open/update
                            except ElementClickInterceptedException:
                                log_callback(f"[{city}] Hours trigger click intercepted (JS). Trying direct click...")
                                try:
                                     # Ensure it's clickable before direct click
                                     clickable_trigger = WebDriverWait(driver, 2).until(EC.element_to_be_clickable(hours_trigger_element))
                                     clickable_trigger.click()
                                     log_callback(f"[{city}] Clicked hours trigger (Direct).")
                                     clicked = True
                                     time.sleep(random.uniform(1.8, 2.8))
                                except Exception as e_direct_click:
                                     log_callback(f"[{city}] Direct click also failed: {e_direct_click}")
                            except Exception as e_click_hours:
                                log_callback(f"[{city}] Error clicking hours trigger: {e_click_hours}")
                        else:
                             log_callback(f"[{city}] Could not find a clickable hours trigger.")

                        # 3. Find and extract from detailed panel if clicked (or sometimes visible by default)
                        # We check for the panel even if not clicked, as it might be visible initially
                        log_callback(f"[{city}] Looking for detailed hours panel/table...")
                        for method, selector in hours_panel_selectors:
                            try:
                                panel = WebDriverWait(driver, 3).until(EC.visibility_of_element_located((method, selector)))
                                hours_panel_element = panel
                                log_callback(f"[{city}] Found detailed hours panel (Selector: {selector})")
                                break
                            except TimeoutException: continue
                            except StaleElementReferenceException: continue
                            except Exception: continue

                        if hours_panel_element:
                            try:
                                hours_text = hours_panel_element.text
                                if hours_text:
                                    # Clean the extracted text
                                    cleaned_hours = re.sub(r'\s*\n\s*', '\n', hours_text).strip() # Consolidate whitespace/newlines
                                    cleaned_hours = cleaned_hours.replace("Sao chép giờ mở cửa", "").replace("Copy opening hours", "") # Remove copy text
                                    cleaned_hours = re.sub(r'(Suggest new hours|Suggest an edit|Đề xuất chỉnh sửa).*', '', cleaned_hours, flags=re.DOTALL | re.IGNORECASE).strip() # Remove suggestions
                                    cleaned_hours = re.sub(r'(^Hours\n)|(\nHours$)', '', cleaned_hours, flags=re.IGNORECASE).strip() # Remove leading/trailing "Hours" lines
                                    cleaned_hours = re.sub(r'\n{2,}', '\n', cleaned_hours).strip() # Remove multiple blank lines
                                    # Remove aria labels sometimes included in text
                                    cleaned_hours = re.sub(r'aria-label="[^"]+"\s*', '', cleaned_hours).strip()

                                    if cleaned_hours:
                                        opening_hours = cleaned_hours
                                        log_callback(f"[{city}] Extracted detailed hours:\n{opening_hours}")
                                        hours_found = True
                                    else:
                                        log_callback(f"[{city}] Detailed hours panel text was empty after cleaning.")
                                        if opening_hours == "Không tìm thấy thông tin giờ" and hours_summary_text:
                                             opening_hours = hours_summary_text # Fallback to summary if panel empty
                                             log_callback(f"[{city}] Using summary as fallback after empty panel.")
                                else:
                                    log_callback(f"[{city}] Detailed hours panel was found but had no text.")
                                    if opening_hours == "Không tìm thấy thông tin giờ" and hours_summary_text:
                                         opening_hours = hours_summary_text # Fallback to summary if panel empty
                                         log_callback(f"[{city}] Using summary as fallback after finding empty panel.")

                            except StaleElementReferenceException:
                                opening_hours = "Lỗi Stale lấy text giờ"
                                log_callback(f"[{city}] {opening_hours}")
                            except Exception as e_get_text:
                                opening_hours = f"Lỗi lấy text giờ: {e_get_text}"
                                log_callback(f"[{city}] {opening_hours}")
                        else:
                            log_callback(f"[{city}] Detailed hours panel/table not found.")
                            # If panel not found, rely on previously found summary text
                            if opening_hours == "Không tìm thấy thông tin giờ" and hours_summary_text:
                                 opening_hours = hours_summary_text
                                 log_callback(f"[{city}] Using initial summary as hours.")


                        # 4. Final Fallback if detailed extraction failed/not found AND summary wasn't found earlier
                        if not hours_found and opening_hours == "Không tìm thấy thông tin giờ":
                            # Last resort: Try aria-label of the trigger itself if found
                            try:
                                if hours_trigger_element:
                                    aria_label_hours = hours_trigger_element.get_attribute('aria-label')
                                    # Basic cleaning of aria-label
                                    if aria_label_hours and ('Hour' in aria_label_hours or 'Open' in aria_label_hours or 'Closed' in aria_label_hours):
                                        # More specific cleaning
                                        cleaned_aria = re.sub(r'(?:Hide|Expand) open hours for the week\s*[:-]?\s*', '', aria_label_hours, flags=re.IGNORECASE).strip()
                                        cleaned_aria = re.sub(r'^Hours\s*[:-]?\s*', '', cleaned_aria, flags=re.IGNORECASE).strip()
                                        cleaned_aria = cleaned_aria.replace(';', '\n').replace(',', '\n').strip() # Break potential lists
                                        cleaned_aria = re.sub(r'\s*\n\s*', '\n', cleaned_aria).strip()
                                        if cleaned_aria and len(cleaned_aria) > 5:
                                             opening_hours = cleaned_aria
                                             log_callback(f"[{city}] Sử dụng aria-label của trigger làm fallback:\n{opening_hours}")
                                             hours_found = True # Considered found via fallback
                                        else:
                                            log_callback(f"[{city}] Aria-label của trigger trống hoặc không hữu ích sau khi làm sạch.")
                                else:
                                    log_callback(f"[{city}] Không có trigger element để thử fallback aria-label.")
                            except Exception as e_aria_fallback:
                                log_callback(f"[{city}] Lỗi khi lấy aria-label giờ fallback: {e_aria_fallback}")

                    except Exception as e_hours_outer:
                         log_callback(f"[{city}] Lỗi không xác định khi xử lý giờ mở cửa: {e_hours_outer}")
                         # Keep default "Không tìm thấy thông tin giờ" if outer error

                    # Ensure final value isn't empty if intended to be 'not found'
                    if not opening_hours or opening_hours.isspace():
                        opening_hours = "Không tìm thấy thông tin giờ"

                # --- Append Data for this item ---
                data_to_append = {
                    "Thành phố": city,
                    "Tên công ty": name,
                    "Địa chỉ": address,
                    "Số điện thoại": phone_number,
                    "Website": domain_name, # Append the extracted domain name
                    "Giờ hoạt động": opening_hours,
                    "Google Maps URL": original_gmaps_url,
                    "Vĩ độ": lat,
                    "Kinh độ": lng,
                    #"Full Website URL": website_url_full # Optional: include full URL if needed
                    "Notes": "CAPTCHA Blocked" if captcha_skipped else ("Data Error" if item_error else "") # Add notes column
                }
                city_data.append(data_to_append)

                # Log summary of appended data
                hours_summary_log = ' '.join(opening_hours.splitlines()[:1]) if isinstance(opening_hours, str) and '\n' in opening_hours else opening_hours
                log_msg = f"[{city}] -> Đã thêm: {name[:40]}... (Domain: {domain_name}, Lat: {lat}, Lng: {lng}, Hours: {str(hours_summary_log)[:30]}...)"
                if captcha_skipped: log_msg += " [CAPTCHA SKIPPED]"
                elif item_error: log_msg += " [DATA ERROR]"
                log_callback(log_msg)

            except Exception as e_proc:
                log_callback(f"[{city}] !!! LỖI NGHIÊM TRỌNG khi xử lý KQ {i + 1} ({aria_name}) !!!")
                log_callback(traceback.format_exc())
                # Append error entry for this item
                city_data.append({
                    "Thành phố": city, "Tên công ty": aria_name,
                    "Địa chỉ": "Lỗi xử lý kết quả", "Số điện thoại": "Lỗi xử lý kết quả",
                    "Website": "Lỗi xử lý kết quả", "Giờ hoạt động": "Lỗi xử lý kết quả",
                    "Google Maps URL": original_gmaps_url, "Vĩ độ": "Lỗi", "Kinh độ": "Lỗi",
                    "Notes": "Processing Error"
                })
            finally:
                # --- Navigate Away Safely (even if error/CAPTCHA occurred) ---
                log_callback(f"[{city}] Chuẩn bị điều hướng khỏi trang chi tiết (KQ {i+1})...")
                try:
                    # Short linger can sometimes help avoid detection
                    # linger_time = random.uniform(0.5, 1.2)
                    # time.sleep(linger_time)

                    # Try navigating back to the search results page
                    log_callback(f"[{city}] Thử điều hướng quay lại bằng driver.back()...")
                    driver.back()
                    log_callback(f"[{city}] Chờ xác nhận đã quay lại trang kết quả/tìm kiếm...")
                    # Wait for elements indicating we are back on search/results page
                    WebDriverWait(driver, 12).until( # Moderate wait for back navigation
                        EC.any_of(
                            EC.presence_of_element_located((By.ID, "searchboxinput")), # Maps search box
                            EC.presence_of_element_located((By.XPATH, "//div[contains(@aria-label, 'Results for')]")), # Results panel
                            EC.presence_of_element_located((By.NAME, "q")) # Google search page (unlikely but possible)
                        )
                    )
                    log_callback(f"[{city}] Xác nhận đã quay lại.")
                    time.sleep(random.uniform(0.8, 1.8)) # Short pause after back navigation

                except TimeoutException:
                    log_callback(f"[{city}] CẢNH BÁO: driver.back() timeout khi chờ xác nhận. Thử tải lại trang tìm kiếm chính (có thể mất trạng thái scroll).")
                    try:
                        # Re-load base maps URL - less ideal as scroll state is lost
                        driver.get("https://www.google.com/maps")
                        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchboxinput")))
                        log_callback(f"[{city}] Đã điều hướng tới maps.google.com (fallback sau timeout back).")
                        # Decide if we should break the loop for the city here as scroll is lost
                        log_callback(f"[{city}] CẢNH BÁO: Trạng thái scroll bị mất. Có thể bỏ sót kết quả.")
                        # break # Uncomment if losing scroll state means stopping the city is better
                    except Exception as e_nav_fallback_timeout:
                        log_callback(f"[{city}] LỖI: Điều hướng fallback tới maps cũng thất bại: {e_nav_fallback_timeout}. Dừng xử lý thành phố này.")
                        item_error = True # Mark as error and break outer loop
                        break # Stop processing results for this city if recovery fails

                except WebDriverException as e_nav_back:
                     log_callback(f"[{city}] CẢNH BÁO: Lỗi khi thực hiện driver.back(): {e_nav_back}. Thử điều hướng tới maps.google.com.")
                     try:
                         driver.get("https://www.google.com/maps")
                         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "searchboxinput")))
                         log_callback(f"[{city}] Đã điều hướng tới maps.google.com (fallback sau lỗi driver.back).")
                         log_callback(f"[{city}] CẢNH BÁO: Trạng thái scroll bị mất. Có thể bỏ sót kết quả.")
                         # break # Uncomment if losing scroll state means stopping the city is better
                     except Exception as e_nav_fallback_fail:
                          log_callback(f"[{city}] LỖI: Điều hướng fallback tới maps (sau lỗi driver.back) cũng thất bại: {e_nav_fallback_fail}. Dừng xử lý thành phố này.")
                          item_error = True
                          break # Stop processing results for this city

                except Exception as e_generic_nav:
                     log_callback(f"[{city}] Lỗi không xác định trong quá trình điều hướng khỏi trang chi tiết: {e_generic_nav}. Dừng xử lý thành phố này.")
                     item_error = True
                     break # Stop processing results for this city

            # If a critical navigation error occurred that necessitates stopping the city loop
            if item_error and status != "ERROR": # Check if status not already Error
                 status = "ERROR" # Mark city as error
                 break # Exit the for loop processing results for this city


        # --- End of loop processing results for one city ---
        if status not in ["ERROR", "CAPTCHA_EARLY"]: # If no major error or early captcha
            if city_data:
                 status = "OK" # Mark as OK if we got some data
            elif status == "DRIVER_OK": # If driver started but no data/links
                 status = "NO_RESULTS" # Assume no results found

        log_callback(f"--- Hoàn thành thu thập cho: {city} (Status: {status}) ---")
        return city_data, status # Return collected data AND final status for this city

    except WebDriverException as e_wd_main:
         log_callback(f"[{city}] !!! LỖI WebDriver NGHIÊM TRỌNG TRONG scrape_city !!!")
         try: log_callback(f"Error message: {e_wd_main.msg}") # Try to get message
         except: pass
         log_callback(traceback.format_exc())
         if driver and "disconnected" in str(e_wd_main).lower():
              log_callback(f"[{city}] Trình duyệt có thể đã đóng hoặc mất kết nối.")
         status = "ERROR"
         return [], status # Return empty list and error status
    except Exception as e_main:
         log_callback(f"[{city}] !!! LỖI CHUNG NGHIÊM TRỌNG TRONG scrape_city !!!")
         log_callback(traceback.format_exc())
         status = "ERROR"
         return [], status # Return empty list and error status
    finally:
        if driver:
            try:
                log_callback(f"[{city}] Đóng trình duyệt...")
                driver.quit()
                log_callback(f"[{city}] Đã đóng trình duyệt.")
            except Exception as e_quit:
                log_callback(f"[{city}] Lỗi khi đóng trình duyệt: {e_quit}")