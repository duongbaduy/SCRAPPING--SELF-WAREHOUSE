# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
from urllib.parse import urlparse, parse_qs, urlsplit
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    WebDriverException # Added for navigation errors
)
import traceback # For detailed error printing

# Danh sách các thành phố lớn tại Úc
cities = [
    "Sydney",
    # "Melbourne", # Add more cities if needed
    # "Brisbane"
]

# Hàm thu thập dữ liệu
def scrape_city(city):
    search_query = f"Self Storage {city} Australia"
    print(f"--- Bắt đầu thu thập dữ liệu cho: {city} ---")

    # --- Options ---
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Uncomment để chạy ẩn
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=en-US") # Use English for more consistent selectors
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        # Khởi tạo WebDriver
        print(f"[{city}] Khởi tạo trình duyệt Chrome...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        print(f"[{city}] Trình duyệt đã khởi tạo.")

        # Stealth settings
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
            """
        })

        driver.get("https://www.google.com/maps")
        print(f"[{city}] Đã mở Google Maps.")
        time.sleep(4) # Chờ trang load cơ bản

        # --- Handle Consent ---
        try:
            # Using a more specific selector combining text and potential attributes
            consent_locator = (By.XPATH, "//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Reject all') or contains(text(), 'I agree')]] | //button[@aria-label='Accept all' or @aria-label='Reject all' or @aria-label='Agree'] | //form[contains(@action, 'consent')]//button[span]")
            consent_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable(consent_locator))
            try:
                consent_button.click()
                print(f"[{city}] Đã nhấp nút consent.")
            except ElementClickInterceptedException:
                 print(f"[{city}] Click consent bị chặn, thử Javascript...")
                 driver.execute_script("arguments[0].click();", consent_button)
                 print(f"[{city}] Đã nhấp nút consent bằng JS.")
            time.sleep(2)
        except TimeoutException:
            print(f"[{city}] Không tìm thấy nút consent hoặc không cần thiết.")
        except Exception as e:
            print(f"[{city}] Lỗi khi xử lý consent: {e}")
            # print(traceback.format_exc()) # Uncomment for detailed consent errors

        # --- Search ---
        try:
            search_box = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "searchboxinput")))
            search_box.clear()
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.ENTER)
            print(f"[{city}] Đã tìm kiếm: {search_query}")
            # Wait for the results list container OR the first result link
            WebDriverWait(driver, 20).until(
                 EC.any_of(
                     EC.presence_of_element_located((By.XPATH, "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]")),
                     EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/maps/place/')]"))
                 )
            )
            print(f"[{city}] Kết quả tìm kiếm đã bắt đầu xuất hiện.")
            time.sleep(5) # Allow results list to populate initially
        except Exception as e_search:
            print(f"[{city}] Lỗi nghiêm trọng khi thực hiện tìm kiếm: {e_search}")
            print(traceback.format_exc())
            raise # Re-raise critical error

        # --- Scroll ---
        scroll_attempts = 0
        max_scroll_attempts = 10 # Allow more scrolls if needed
        # Scroll the div containing the results list, identified by aria-label
        feed_scroll_selector = "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]/parent::div"
        try:
            feed_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, feed_scroll_selector))
            )
            print(f"[{city}] Bắt đầu scroll panel kết quả...")
            last_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
            no_change_count = 0
            # XPath for the "end of list" message (can be span or p tag)
            end_of_list_xpath = "//span[contains(text(), \"You've reached the end of the list.\")] | //p[contains(., \"You've reached the end of the list.\")]"

            while scroll_attempts < max_scroll_attempts:
                # Check if 'end of the list' message is visible
                try:
                     end_elements = driver.find_elements(By.XPATH, end_of_list_xpath)
                     is_end_visible = any(el.is_displayed() for el in end_elements)
                     if is_end_visible:
                         print(f"[{city}] Phát hiện thông báo cuối danh sách. Dừng scroll.")
                         break
                except NoSuchElementException:
                    pass # Expected if not at the end

                # Scroll down using JS, targeting the specific feed element
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed_element)
                print(f"[{city}] Đã scroll lần {scroll_attempts + 1}...")
                time.sleep(3.5) # Wait for content to load - adjust if needed

                # Calculate new scroll height and compare
                try:
                    new_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
                except Exception as e_scroll_height:
                    print(f"[{city}] Lỗi khi lấy scrollHeight, có thể element bị stale. Thử tìm lại...")
                    try:
                        feed_element = driver.find_element(By.XPATH, feed_scroll_selector) # Try finding again
                        new_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
                    except Exception as e_refind:
                         print(f"[{city}] Tìm lại element scroll cũng lỗi ({e_refind}). Dừng scroll.")
                         break # Stop scrolling if element cannot be found/accessed

                if new_height == last_height:
                    no_change_count += 1
                    print(f"[{city}] Chiều cao không đổi (lần {no_change_count}).")
                     # Check end message again after height check confirms no change
                    try:
                         end_elements = driver.find_elements(By.XPATH, end_of_list_xpath)
                         is_end_visible = any(el.is_displayed() for el in end_elements)
                         if is_end_visible:
                             print(f"[{city}] Chiều cao không đổi VÀ thấy thông báo cuối danh sách. Dừng scroll.")
                             break
                    except NoSuchElementException:
                        pass
                    # Stop if height hasn't changed for a few consecutive attempts
                    if no_change_count >= 3:
                        print(f"[{city}] Chiều cao không đổi {no_change_count} lần liên tiếp. Dừng scroll.")
                        break
                else:
                    no_change_count = 0 # Reset counter if height changed
                    last_height = new_height

                scroll_attempts += 1

            if scroll_attempts == max_scroll_attempts:
                 print(f"[{city}] Đạt số lần scroll tối đa ({max_scroll_attempts}).")

        except TimeoutException:
            print(f"[{city}] Không tìm thấy panel kết quả để scroll ({feed_scroll_selector}). Có thể không có kết quả.")
        except Exception as e:
             print(f"[{city}] Lỗi khi scroll: {e}")
             print(traceback.format_exc())


        # --- Get Result Links ---
        # XPath to find the 'a' tags that are direct children of result divs and contain place links
        results_xpath = "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]/div/div[.//a[contains(@href, '/maps/place/')]]/a[@aria-label and contains(@href, '/maps/place/')]"
        result_links = []
        processed_links = set()
        MAX_RESULTS_TO_COLLECT = 200 # Collect up to 200 links initially
        try:
            # Wait for at least one result link to be present after scrolling
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, results_xpath))
            )
            potential_results = driver.find_elements(By.XPATH, results_xpath)
            print(f"[{city}] Tìm thấy {len(potential_results)} thẻ 'a' tiềm năng sau scroll.")

            for res in potential_results:
                 try:
                     href = res.get_attribute('href')
                     aria_label = res.get_attribute('aria-label')
                     # Basic validation and check for duplicates
                     if href and href.startswith("https://www.google.com/maps/place/") and aria_label and href not in processed_links:
                         result_links.append({'href': href, 'aria_label': aria_label})
                         processed_links.add(href)
                         if len(result_links) >= MAX_RESULTS_TO_COLLECT:
                             print(f"[{city}] Đã thu thập đủ {MAX_RESULTS_TO_COLLECT} link.")
                             break
                 except StaleElementReferenceException:
                     print(f"[{city}] Bỏ qua phần tử link bị stale khi lấy href/label.")
                     continue
                 except Exception as e_link_attr:
                     print(f"[{city}] Lỗi khi lấy thuộc tính link: {e_link_attr}")
                     continue # Skip this link

            print(f"[{city}] Thu thập được {len(result_links)} link kết quả hợp lệ.")

        except TimeoutException:
             print(f"[{city}] Không tìm thấy link kết quả nào ({results_xpath}) sau khi scroll/chờ.")
        except Exception as e:
            print(f"[{city}] Lỗi khi thu thập link kết quả: {e}")
            print(traceback.format_exc())

        # --- Process Each Result ---
        city_data = []
        if not result_links:
             print(f"[{city}] Không có link kết quả nào để xử lý.")

        MAX_RESULTS_TO_PROCESS = 20 # Define the actual limit for detailed processing

        for i, res_info in enumerate(result_links):
            # Stop if the processing limit is reached
            if i >= MAX_RESULTS_TO_PROCESS:
                print(f"[{city}] Đã đạt giới hạn xử lý {MAX_RESULTS_TO_PROCESS} kết quả.")
                break

            print(f"\n[{city}] === Đang xử lý Kết quả {i + 1}/{min(len(result_links), MAX_RESULTS_TO_PROCESS)} ===")
            original_gmaps_url = res_info.get('href', 'Lỗi lấy URL')
            print(f"[{city}] Tên (từ link): {res_info.get('aria_label', 'N/A')}")
            print(f"[{city}] URL Gmaps gốc: {original_gmaps_url}")

            # --- Initialize data fields for each result ---
            name = res_info.get('aria_label', "Lỗi lấy tên") # Use name from link as initial default
            address = "Lỗi lấy địa chỉ"
            phone_number = "Lỗi lấy SĐT"
            website_url_full = "Chưa kiểm tra" # Will be updated if found
            domain_name = "Chưa kiểm tra"      # Will be updated if found
            opening_hours = "Chưa lấy từ GMap" # Default for GMap hours
            lat, lng = "", ""                  # Initialize Lat/Lng

            try:
                # --- Navigate to Google Maps Detail Page ---
                print(f"[{city}] Đang điều hướng tới: {original_gmaps_url}")
                driver.get(original_gmaps_url)
                detail_page_url = "" # Initialize detail page URL
                try:
                     # Wait for H1 or main content area to be somewhat loaded
                     WebDriverWait(driver, 15).until(
                         EC.any_of(
                             EC.visibility_of_element_located((By.TAG_NAME, "h1")),
                             EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']"))
                         )
                     )
                     print(f"[{city}] Trang chi tiết Gmaps đã tải (thấy H1 hoặc main content).")
                     time.sleep(1.5) # Pause slightly longer after load confirmation
                     detail_page_url = driver.current_url # Get the possibly updated URL
                     print(f"[{city}] URL hiện tại sau khi tải: {detail_page_url}")

                except TimeoutException:
                     print(f"[{city}] CẢNH BÁO: Trang chi tiết Gmaps tải chậm hoặc không có H1/main content trong 15s.")
                     detail_page_url = driver.current_url # Get URL anyway
                     print(f"[{city}] URL hiện tại (sau timeout): {detail_page_url}")
                     time.sleep(5) # Give extra time if load was problematic

                # --- Extract Lat/Lng ---
                # (Prioritize current URL, fallback to original, then JS)
                lat, lng = "", ""
                coords_found = False
                try:
                    url_to_check_primary = detail_page_url if detail_page_url else original_gmaps_url
                    print(f"[{city}] Đang kiểm tra tọa độ trong URL: {url_to_check_primary}")
                    # Method 1: Look for @lat,lng format
                    url_pattern = re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+)')
                    coords_match = url_pattern.search(url_to_check_primary)
                    if coords_match:
                        lat = coords_match.group(1)
                        lng = coords_match.group(2)
                        print(f"[{city}] Đã trích xuất tọa độ từ URL (@): Lat {lat}, Lng {lng}")
                        coords_found = True
                    else:
                        # Method 2: Look for data=!3dlat!4dlng format (handles %21 encoding too)
                        data_pattern = re.compile(r'data=.*?(!3d|%213d)(-?\d+\.\d+).*?(!4d|%214d)(-?\d+\.\d+)')
                        data_match = data_pattern.search(url_to_check_primary)
                        if data_match:
                            lat = data_match.group(2) # Latitude value
                            lng = data_match.group(4) # Longitude value
                            print(f"[{city}] Đã trích xuất tọa độ từ URL (data=): Lat {lat}, Lng {lng}")
                            coords_found = True

                    # Method 3: Fallback to the *other* URL if not found in primary and URLs differ
                    if not coords_found and detail_page_url and original_gmaps_url != detail_page_url:
                        url_to_check_secondary = original_gmaps_url
                        print(f"[{city}] Không tìm thấy trong URL chính, thử URL gốc: {url_to_check_secondary}")
                        coords_match = url_pattern.search(url_to_check_secondary) # Check original URL (@)
                        if coords_match:
                            lat = coords_match.group(1); lng = coords_match.group(2)
                            print(f"[{city}] Đã trích xuất tọa độ từ URL GỐC (@): Lat {lat}, Lng {lng}")
                            coords_found = True
                        else:
                            data_match = data_pattern.search(url_to_check_secondary) # Check original URL (data=)
                            if data_match:
                                lat = data_match.group(2); lng = data_match.group(4)
                                print(f"[{city}] Đã trích xuất tọa độ từ URL GỐC (data=): Lat {lat}, Lng {lng}")
                                coords_found = True

                    # Method 4: Fallback to JavaScript method (less reliable)
                    if not coords_found:
                         print(f"[{city}] Không tìm thấy tọa độ trong URL, thử fallback JavaScript...")
                         try:
                            time.sleep(2) # Give page time to potentially load JS variables
                            # JS to find coords in meta tag or LD+JSON script
                            location_script = """
                                var loc = document.querySelector('meta[property="og:image"]');
                                if (loc) { var imgSrc = loc.getAttribute('content'); var match = imgSrc.match(/center=([^&]+)/); return match ? match[1] : null; }
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                for (const script of scripts) { try { const data = JSON.parse(script.textContent); if (data && data.geo && data.geo.latitude && data.geo.longitude) { return data.geo.latitude + ',' + data.geo.longitude; } } catch (e) {} }
                                return null;"""
                            center_param = driver.execute_script(location_script)
                            if center_param and ',' in center_param:
                                coords = center_param.split(',')
                                if len(coords) >= 2:
                                    lat_cand = coords[0].strip(); lng_cand = coords[1].strip()
                                    # Validate format
                                    if re.match(r'^-?\d+\.\d+$', lat_cand) and re.match(r'^-?\d+\.\d+$', lng_cand):
                                        lat = lat_cand; lng = lng_cand
                                        print(f"[{city}] Đã trích xuất tọa độ từ page source (JS fallback): Lat {lat}, Lng {lng}")
                                        coords_found = True
                                    else: print(f"[{city}] Giá trị JS fallback không hợp lệ: {center_param}")
                                else: print(f"[{city}] Không thể phân tích tọa độ từ center_param (JS fallback): {center_param}")
                            else: print(f"[{city}] Không tìm thấy tọa độ qua JS fallback (meta/script).")
                         except Exception as e_coords_js: print(f"[{city}] Lỗi khi cố gắng lấy tọa độ từ page (JS fallback): {e_coords_js}")

                    # Final check if coordinates were found
                    if not coords_found:
                        print(f"[{city}] CẢNH BÁO: Không thể trích xuất tọa độ bằng mọi phương pháp.")
                        lat, lng = "Không tìm thấy", "Không tìm thấy" # Set placeholder

                except Exception as e_coords:
                    lat, lng = "Lỗi tọa độ", "Lỗi tọa độ" # Set error placeholder
                    print(f"[{city}] Lỗi chung khi trích xuất tọa độ: {e_coords}")
                    # print(traceback.format_exc()) # Uncomment for detail if needed

                # --- Get Name (from H1) ---
                # Use H1 text if available and seems valid, otherwise keep name from link
                try:
                    # Wait up to 8 seconds for H1 to be visible <<< INCREASED WAIT TIME
                    name_element = WebDriverWait(driver, 8).until(EC.visibility_of_element_located((By.TAG_NAME, "h1")))
                    fetched_name = name_element.text.strip()
                    if fetched_name: # Check if H1 text is not empty
                        name = fetched_name # Update name if H1 is found
                    print(f"[{city}] Tên (H1): {name}")
                except TimeoutException: print(f"[{city}] Không tìm thấy H1 trong 8s. Giữ tên từ aria-label.") # Updated message
                except NoSuchElementException: print(f"[{city}] Không tìm thấy H1. Giữ tên từ aria-label.")
                except Exception as e_name: print(f"[{city}] Lỗi khi lấy tên từ H1: {e_name}.")


                # --- Get Address ---
                # Assume 'driver' is your initialized WebDriver instance
                # Assume 'city' is defined elsewhere for logging

                address = "Không lấy được địa chỉ" # Default error message
                address_source = "N/A" # To track how the address was obtained
                address_found = False # Flag to indicate if address was found

                # --- METHOD 1: Primary Button (data-item-id) -> aria-label -> inner text ---
                try:
                    print(f"[{city}] Bắt đầu Method 1: Tìm button[data-item-id='address']...")
                    button_locator = (By.CSS_SELECTOR, "button[data-item-id='address']")
                    # INCREASED WAIT TIME slightly
                    address_button = WebDriverWait(driver, 12).until(
                        EC.visibility_of_element_located(button_locator)
                    )
                    print(f"[{city}] Method 1: Tìm thấy button[data-item-id='address'].")

                    # Attempt 1a: Get from ARIA-LABEL
                    try:
                        aria_label_text = address_button.get_attribute('aria-label')
                        if aria_label_text and 'Address: ' in aria_label_text:
                            address = aria_label_text.replace('Address: ', '').strip()
                            if address: # Check if address is not empty after stripping
                                address_source = "Method 1a: aria-label"
                                address_found = True
                                print(f"[{city}] Địa chỉ ({address_source}): {address}")
                            else:
                                print(f"[{city}] Method 1a: aria-label sau khi làm sạch bị trống.")
                        else:
                            print(f"[{city}] Method 1a: aria-label không có 'Address: ' hoặc trống: '{aria_label_text}'.")
                    except Exception as e_aria:
                        print(f"[{city}] Method 1a: Lỗi khi lấy aria-label: {e_aria}.")

                    # Attempt 1b: Get from INNER TEXT (Only if aria-label failed)
                    if not address_found:
                        print(f"[{city}] Method 1b: Thử lấy inner text từ button...")
                        try:
                            inner_div_locator = (By.CSS_SELECTOR, "div.Io6YTe, div.QsDR1c") # Keep both as potential inner divs
                            address_element = address_button.find_element(*inner_div_locator)
                            inner_text = address_element.text.strip()
                            if inner_text and len(inner_text) > 5: # Basic check for meaningful text
                                address = inner_text
                                address_source = "Method 1b: inner text (div.Io6YTe/QsDR1c)"
                                address_found = True
                                print(f"[{city}] Địa chỉ ({address_source}): {address}")
                            else:
                                print(f"[{city}] Method 1b: Inner text tìm thấy nhưng trống hoặc quá ngắn.")
                        except NoSuchElementException:
                            print(f"[{city}] Method 1b: Không tìm thấy inner div (Io6YTe/QsDR1c) bên trong button.")
                        except Exception as e_inner:
                            print(f"[{city}] Method 1b: Lỗi khi lấy inner text: {e_inner}")

                # --- Handle failure of Method 1 (Button not found or no address extracted from it) ---
                except TimeoutException:
                    print(f"[{city}] Method 1: Không tìm thấy button[data-item-id='address'] trong 12s.")
                    # address_found remains False, proceed to Method 2
                except Exception as e_addr_m1:
                    print(f"[{city}] Method 1: Lỗi không xác định: {e_addr_m1}")
                    # address_found remains False, proceed to Method 2

                # --- METHOD 2: Direct Div Search (Specific Class - if Method 1 failed) ---
                if not address_found:
                    print(f"[{city}] Bắt đầu Method 2: Tìm trực tiếp div.Io6YTe.fontBodyMedium.kR99db.fdkmkc...")
                    try:
                        # Use precise class combination
                        # NOTE: CSS selector with spaces in class needs '.' replacement:
                        direct_div_locator = (By.CSS_SELECTOR, "div.Io6YTe.fontBodyMedium.kR99db.fdkmkc")
                        # Wait for the specific div
                        address_div_element = WebDriverWait(driver, 8).until(
                            EC.visibility_of_element_located(direct_div_locator)
                        )
                        direct_text = address_div_element.text.strip()
                        if direct_text and len(direct_text) > 10: # Check for meaningful address length
                            address = direct_text
                            address_source = "Method 2: Direct Div (Io6YTe...)"
                            address_found = True
                            print(f"[{city}] Địa chỉ ({address_source}): {address}")
                        else:
                            print(f"[{city}] Method 2: Tìm thấy div trực tiếp nhưng text trống hoặc quá ngắn: '{direct_text}'")
                    except TimeoutException:
                        print(f"[{city}] Method 2: Không tìm thấy div trực tiếp (Io6YTe...) trong 8s.")
                    except Exception as e_addr_m2:
                        print(f"[{city}] Method 2: Lỗi khi tìm div trực tiếp: {e_addr_m2}")

                # --- METHOD 3: Complex Fallback (XPath - if Method 1 & 2 failed) ---
                if not address_found:
                    print(f"[{city}] Bắt đầu Method 3: Thử fallback phức tạp (XPath)...")
                    try:
                        # Your original complex XPath
                        address_alt_locator = (By.XPATH, "//img[contains(@src,'ic_pin_place')]//ancestor::button/following-sibling::div[contains(@class,'Io6YTe')] | //button[contains(@aria-label, 'Address')]/div[contains(@class,'Io6YTe')] | //div[contains(@class,'Io6YTe')][string-length(normalize-space(.)) > 5 and (contains(., ' St') or contains(., ' Rd') or contains(., ' NSW'))]")
                        # Using visibility_of_any_elements_located might be less reliable, let's try finding elements directly after a small wait
                        WebDriverWait(driver, 5).until(lambda d: d.find_elements(*address_alt_locator)) # Wait until at least one element is found
                        address_elements = driver.find_elements(*address_alt_locator)

                        if address_elements:
                            print(f"[{city}] Method 3: Tìm thấy {len(address_elements)} phần tử ứng viên bằng XPath.")
                            found_in_fallback = False
                            for el in address_elements:
                                # Check visibility *and* get text in one go to avoid stale elements
                                try:
                                    if el.is_displayed():
                                        addr_text = el.text.strip()
                                        if addr_text and len(addr_text) > 10: # Basic check for meaningful address
                                            address = addr_text
                                            address_source = "Method 3: Complex Fallback XPath"
                                            address_found = True
                                            found_in_fallback = True
                                            print(f"[{city}] Địa chỉ ({address_source}): {address}")
                                            break # Use the first good one found
                                except Exception as e_fallback_el:
                                    print(f"[{city}] Method 3: Lỗi khi kiểm tra phần tử fallback: {e_fallback_el}")
                            if not found_in_fallback:
                                print(f"[{city}] Method 3: XPath tìm thấy phần tử nhưng không có text phù hợp/hiển thị.")
                        else:
                            print(f"[{city}] Method 3: XPath không tìm thấy phần tử nào.")
                    except TimeoutException:
                        print(f"[{city}] Method 3: Không tìm thấy phần tử nào bằng XPath trong 5s.")
                    except Exception as e_addr_fallback:
                        # Catch specific message if available
                        msg = getattr(e_addr_fallback, 'msg', str(e_addr_fallback))
                        print(f"[{city}] Method 3: Lấy địa chỉ fallback phức tạp thất bại: {msg}")


                # --- Final Result ---
                if not address_found:
                    address = "Không lấy được địa chỉ" # Ensure default message if nothing worked
                    address_source = "Thất bại"

                print(f"[{city}] ===> KẾT QUẢ ĐỊA CHỈ: {address} (Nguồn: {address_source})")


                # --- Get Phone Number ---
                # Try specific container, then attributes, then generic tel link
                phone_number = "Không lấy được SĐT" # Default error message
                try:
                    # Primary target: Button or Link with data-item-id starting 'phone:tel:' (Keep wait time moderate)
                    phone_container_locator = (By.CSS_SELECTOR, "a[data-item-id^='phone:tel:'], button[data-item-id^='phone:tel:']")
                    phone_container_element = WebDriverWait(driver, 7).until(EC.presence_of_element_located(phone_container_locator))

                    # Try getting visible text inside the container first
                    try:
                        phone_text_element = phone_container_element.find_element(By.CSS_SELECTOR, "div.Io6YTe, div.QsDR1c")
                        pn_text = phone_text_element.text.strip()
                        # Check if text looks like a phone number (digits, +, (), space, hyphen, min length)
                        if pn_text and re.search(r'[\d\+() -]{7,}', pn_text):
                             phone_number = pn_text
                             print(f"[{city}] SĐT (Text): {phone_number}")
                        else:
                             raise NoSuchElementException # If text isn't phone-like, try attributes
                    except NoSuchElementException:
                        # If no inner text or not phone-like, check attributes of the container
                        aria_label = phone_container_element.get_attribute('aria-label')
                        href = phone_container_element.get_attribute('href') if phone_container_element.tag_name == 'a' else None

                        if href and href.startswith('tel:'):
                            phone_number = href.replace('tel:', '').strip()
                            print(f"[{city}] SĐT (Href): {phone_number}")
                        elif aria_label:
                            # Try extracting from aria-label (e.g., "Phone: +61 2...")
                            # Look for a sequence of digits, spaces, (), -, +
                            match = re.search(r'(\+?\s?[\d\s() -]{8,})', aria_label)
                            if match:
                                phone_number = match.group(1).strip()
                                print(f"[{city}] SĐT (Aria): {phone_number}")
                            else:
                                phone_number = "Lỗi regex SĐT từ Aria" # Regex failed
                        else:
                            phone_number = "Container không có text/href/aria hợp lệ" # No useful info found

                except TimeoutException:
                    print(f"[{city}] Không tìm thấy container SĐT chuẩn (data-item-id). Thử tìm link tel: bất kỳ...")
                    try:
                        # Fallback: Find any link starting with 'tel:'
                        generic_phone_link = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='tel:']")))
                        href = generic_phone_link.get_attribute('href')
                        if href and href.startswith('tel:'):
                            phone_number = href.replace('tel:', '').strip()
                            print(f"[{city}] SĐT (Generic Href): {phone_number}")
                        else:
                            phone_number = "Lỗi href SĐT generic" # Found link but href invalid
                    except TimeoutException:
                         print(f"[{city}] Không tìm thấy link SĐT nào.")
                         phone_number = "Không tìm thấy SĐT (Timeout)" # Final failure state
                except Exception as e_phone:
                    print(f"[{city}] Lỗi không xác định khi lấy SĐT: {e_phone}")
                    # print(traceback.format_exc()) # Uncomment for details
                    phone_number = "Lỗi không xác định khi lấy SĐT"


                # --- Get Website URL from Google Maps ---
                # Try multiple selectors, handle redirects, extract domain
                website_url_full = "Không có trang web" # Default
                domain_name = "Không có trang web"      # Default
                try:
                    # List of selectors (CSS and XPath) to find the website link element
                    website_selectors = [
                        "a[data-item-id='authority'][href^='http']",      # Primary website link attribute
                        "a[aria-label*='Website:'][href^='http']",        # Link with "Website:" in aria-label
                        "button[aria-label*='Website:']",                # Button that might reveal link (less common now)
                        "a[href*='://'][data-tooltip*='website' i]",      # Link with "website" in tooltip
                        "a[href*='://'][aria-label*='website' i]",       # Link with "website" in aria-label
                         # XPath: Find website icon (globe), go up ancestor divs, find link sibling/descendant
                        "//img[contains(@src,'ic_public')]//ancestor::div[2]//a[@href^='http']",
                        # XPath: Find button with 'Website' label, go to parent, find sibling div, find link inside
                        "//button[contains(@aria-label, 'Website')]//ancestor::div[1]//following-sibling::div//a[@href^='http']",
                    ]
                    found_url = None # Stores the raw href found
                    found_element = None # Stores the element itself

                    for selector in website_selectors:
                        try:
                            # Determine if it's CSS or XPath
                            find_method = By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH
                            # Wait briefly for element(s) matching this selector
                            elements = WebDriverWait(driver, 2).until(
                                EC.presence_of_all_elements_located((find_method, selector))
                            )
                            # Iterate through found elements (usually only one)
                            for element in elements:
                                # Prefer visible elements if possible
                                # if not element.is_displayed(): continue
                                href = element.get_attribute('href')
                                # Basic check for http(s) URL
                                if href and href.startswith('http'):
                                    found_url = href
                                    found_element = element # Store the element for potential future interaction
                                    print(f"[{city}] Tìm thấy URL tiềm năng (Selector: {selector}): {found_url}")
                                    # Prioritize non-google redirect links
                                    if '/url?q=' not in found_url:
                                        break # Found a direct link, likely the best, stop searching
                            # If a direct link was found in the inner loop, break outer loop too
                            if found_url and '/url?q=' not in found_url:
                                break
                        except TimeoutException:
                             # This selector didn't find anything within the time limit
                             continue # Try the next selector in the list
                        except StaleElementReferenceException:
                             print(f"[{city}] Phần tử trang web bị stale khi kiểm tra selector '{selector}'.")
                             continue # Try next selector
                        except Exception as e_sel:
                             print(f"[{city}] Lỗi nhỏ khi kiểm tra selector trang web '{selector}': {e_sel}")
                             continue # Try next selector

                    # --- Process the found URL ---
                    if found_url:
                         # Handle Google URL redirects if present
                         if '/url?q=' in found_url:
                              try:
                                   # Parse the URL and extract the 'q' parameter
                                   query_params = parse_qs(urlsplit(found_url).query)
                                   if 'q' in query_params and query_params['q']:
                                       website_url_full = query_params['q'][0] # Get the actual target URL
                                       print(f"[{city}] Trích xuất URL thực từ Google redirect: {website_url_full}")
                                   else:
                                       # If 'q' param extraction fails, use the redirect URL as is
                                       website_url_full = found_url
                                       print(f"[{city}] Giữ lại URL redirect (không trích xuất được q): {website_url_full}")
                              except Exception as e_redirect:
                                   print(f"[{city}] Lỗi khi xử lý Google redirect URL: {e_redirect}")
                                   website_url_full = found_url # Fallback to the raw redirect URL on error
                         else:
                              # It's a direct URL
                              website_url_full = found_url
                              print(f"[{city}] Trang web trực tiếp: {website_url_full}")

                         # <<< START DOMAIN EXTRACTION >>>
                         # Ensure we have a valid http(s) URL before parsing
                         if website_url_full and website_url_full.startswith('http'):
                             try:
                                 parsed_uri = urlparse(website_url_full)
                                 # Get network location (domain), convert to lower case
                                 netloc = parsed_uri.netloc.lower()
                                 # Remove 'www.' prefix if it exists
                                 if netloc.startswith('www.'):
                                     domain_name = netloc[4:]
                                 else:
                                     domain_name = netloc
                                 # Remove trailing slash if present (less common in netloc)
                                 domain_name = domain_name.rstrip('/')
                                 print(f"[{city}] Trích xuất tên miền: {domain_name}")
                             except Exception as e_parse:
                                 print(f"[{city}] Lỗi khi phân tích URL trang web thành tên miền: {e_parse}")
                                 domain_name = "Lỗi phân tích URL" # Set error state
                         else:
                              # If website_url_full is somehow invalid after processing
                              domain_name = "Không có trang web (URL không hợp lệ)"
                         # <<< END DOMAIN EXTRACTION >>>
                    else:
                         # No website link found using any selector
                         print(f"[{city}] Không tìm thấy link trang web trên Google Maps sau các lần thử.")
                         website_url_full = "Không có trang web"
                         domain_name = "Không có trang web"

                except Exception as e_website_find:
                    # Catch any unexpected error during the website finding process
                    print(f"[{city}] Lỗi chung khi tìm link trang web trên Google Maps: {e_website_find}")
                    print(traceback.format_exc())
                    website_url_full = "Lỗi tìm trang web"
                    domain_name = "Lỗi tìm trang web"


                # --- Get Opening Hours from Google Maps ---
                opening_hours = "Không lấy được giờ từ GMap" # Reset default state
                try:
                    # Strategy:
                    # 1. Find the clickable trigger element (button/div containing current hours summary).
                    # 2. Click the trigger using JavaScript.
                    # 3. MANUALLY Wait for the detailed hours table (like the one provided) to appear by checking selectors individually.
                    # 4. Extract text from the table.

                    hours_panel_element = None # Will store the final detailed hours element

                    # --- Define Selectors ---
                    # Selectors for the DETAILED hours table/container THAT APPEARS AFTER CLICKING
                    hours_container_selectors_after_click = [
                        (By.XPATH, "//table[contains(@class, 'eK4R0e')]"), # *** Specific table class from example ***
                        (By.XPATH, "//div[contains(@class, 't39EBf')]//table"), # Table inside the specific div class
                        (By.XPATH, "//table[contains(@aria-label, 'Opening hours') or contains(@aria-label, 'giờ mở cửa')]"), # Table with aria-label
                        (By.XPATH, "//div[contains(@aria-label, 'Opening hours') or contains(@aria-label, 'giờ mở cửa')]//div[@role='list']"), # Alt div structure
                        (By.XPATH, "//div[contains(@class, 'm6QErb')]"), # Another potential container class
                    ]

                    # Locators for the element TO CLICK initially to show hours
                    hours_trigger_selectors = [
                        (By.XPATH, "//button[contains(@aria-label, 'Hour')] | //div[@role='button'][contains(@aria-label, 'Hour')] | //button[.//img[contains(@src,'ic_schedule')]] | //div[.//img[contains(@src,'ic_schedule')]][@role='button']"),
                        (By.CSS_SELECTOR, "button[data-item-id^='oh']"),
                        (By.XPATH, "//div[contains(@class, 'AeaXub')][@role='button']"),
                        (By.CSS_SELECTOR, ".AeaXub[role='button'], button.AeaXub"),
                        (By.XPATH, "//div[contains(text(), 'Open') or contains(text(), 'Closed') or contains(text(), 'Mở') or contains(text(), 'Đóng cửa')][string-length(normalize-space(.)) < 50]"),
                    ]
                    # --- End Define Selectors ---

                    # Step 1 & 2: Find and Click the Trigger
                    print(f"[{city}] Tìm nút/div hiển thị giờ để nhấp...")
                    clicked = False
                    hours_trigger_element = None

                    for idx, selector in enumerate(hours_trigger_selectors):
                        try:
                            # Wait up to 5 seconds for each trigger selector <<< INCREASED WAIT TIME
                            trigger_elements = WebDriverWait(driver, 5).until(
                                EC.presence_of_all_elements_located(selector)
                            )
                            visible_triggers = [el for el in trigger_elements if el.is_displayed()]

                            if visible_triggers:
                                hours_trigger_element = visible_triggers[0]
                                print(f"[{city}] Tìm thấy nút bấm giờ tiềm năng (Selector {idx+1}: {selector[1]}). Thử nhấp...")
                                try:
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", hours_trigger_element)
                                    time.sleep(0.5)
                                    driver.execute_script("arguments[0].click();", hours_trigger_element)
                                    print(f"[{city}] Đã nhấp nút bấm giờ.")
                                    clicked = True
                                    time.sleep(1.5) # Wait for panel to open
                                    break # Exit selector loop once clicked
                                except ElementClickInterceptedException:
                                    print(f"[{city}] Click nút giờ bị chặn (Selector {idx+1}: {selector[1]}). Thử selector khác.")
                                except StaleElementReferenceException:
                                     print(f"[{city}] Nút bấm giờ bị stale (Selector {idx+1}: {selector[1]}). Thử selector khác.")
                                except Exception as e_click:
                                    print(f"[{city}] Lỗi khi nhấp nút giờ (Selector {idx+1}: {selector[1]}): {e_click}")
                        except TimeoutException:
                            # print(f"[{city}] Không tìm thấy nút bấm giờ trong 5s (Selector {idx+1}: {selector[1]}).") # Debug line
                            continue # Try next selector
                        except Exception as e_find_trigger:
                            print(f"[{city}] Lỗi khi tìm nút bấm giờ (Selector {idx+1}: {selector[1]}): {e_find_trigger}")
                            continue # Try next selector

                    # Step 3: MANUALLY Wait for the DETAILED Panel/Table *after* clicking
                    if clicked:
                        print(f"[{city}] Chờ panel/bảng giờ chi tiết xuất hiện sau khi nhấp (tối đa ~7s)...")
                        overall_wait_start = time.time()
                        overall_timeout = 7 # seconds

                        while time.time() - overall_wait_start < overall_timeout:
                            for panel_selector in hours_container_selectors_after_click:
                                try:
                                    # Try finding the element using the current selector
                                    found_panels = driver.find_elements(*panel_selector)
                                    # Check if any of the found elements are visible
                                    visible_panels = [p for p in found_panels if p.is_displayed()]
                                    if visible_panels:
                                        hours_panel_element = visible_panels[0] # Take the first visible one
                                        print(f"[{city}] Panel/bảng giờ chi tiết đã xuất hiện (Selector: {panel_selector[1]}).")
                                        # Optional: Prioritize 'eK4R0e' if multiple visible panels match different selectors
                                        for p in visible_panels:
                                             panel_class_attr = p.get_attribute('class') or "" # Handle None case
                                             if 'eK4R0e' in panel_class_attr:
                                                  hours_panel_element = p
                                                  print(f"[{city}] Ưu tiên chọn panel giờ với class 'eK4R0e'.")
                                                  break
                                        break # Exit the inner loop (selectors)
                                except NoSuchElementException:
                                    # find_elements doesn't raise this, but keep for safety/clarity
                                    continue
                                except StaleElementReferenceException:
                                    print(f"[{city}] Panel bị stale khi kiểm tra selector {panel_selector[1]}. Thử lại vòng lặp.")
                                    # Let the outer loop retry
                                    break # Break inner loop to retry outer loop quickly
                                except Exception as e_find_panel:
                                    # Log other potential errors during find_elements/is_displayed
                                    print(f"[{city}] Lỗi nhỏ khi kiểm tra panel selector {panel_selector[1]}: {e_find_panel}")
                                    # Continue checking other selectors in this iteration
                                    continue

                            if hours_panel_element:
                                break # Exit the outer while loop (time-based)

                            # Small pause before checking selectors again
                            time.sleep(0.5)

                        # After the loop, check if we found the panel
                        if not hours_panel_element:
                            try:
                                print(f"[{city}] Thử lấy giờ từ aria-label của div.t39EBf GUrTXd...")
                                fallback_div = driver.find_element(By.CSS_SELECTOR, "div.t39EBf.GUrTXd[aria-label]")
                                aria_label_text = fallback_div.get_attribute("aria-label")
                                if aria_label_text:
                                    opening_hours = aria_label_text.strip()
                                    print(f"[{city}] Lấy giờ từ aria-label thành công:\n{opening_hours}")
                            except Exception as e_aria:
                                print(f"[{city}] Không lấy được aria-label fallback: {e_aria}")


                    elif hours_trigger_element is None: # If no trigger was found at all
                         print(f"[{city}] Không tìm thấy nút/thông tin giờ nào để nhấp vào.")
                         opening_hours = "Không tìm thấy thông tin giờ ban đầu trên GMap"
                    # else: # Trigger found but click failed (handled by 'clicked' flag)


                    # Step 4: Extract text if panel element was successfully found
                    if hours_panel_element: # Check if we successfully got the panel element from the manual wait
                        try:
                            # Get all text within the located panel/table element
                            time.sleep(0.5) # Small delay before getting text
                            hours_text = hours_panel_element.text
                            if hours_text:
                                # Clean the extracted text
                                opening_hours = re.sub(r'\s*\n\s*', '\n', hours_text).strip()
                                # Remove potential "Copy opening hours" text (adjust if needed)
                                opening_hours = opening_hours.replace("Sao chép giờ mở cửa", "").strip()
                                opening_hours = opening_hours.replace("Copy opening hours", "").strip()
                                # Clean again after replacement
                                opening_hours = re.sub(r'\n+', '\n', opening_hours).strip()

                                print(f"[{city}] Giờ hoạt động trích xuất từ GMap:\n{opening_hours}")
                            else:
                                # Panel found but contains no text content
                                opening_hours = "Panel giờ chi tiết trống"
                                print(f"[{city}] Panel/bảng giờ chi tiết tìm thấy nhưng không có text.")
                        except StaleElementReferenceException:
                             print(f"[{city}] Lỗi: Panel giờ chi tiết bị stale khi đang lấy text.")
                             opening_hours = "Lỗi lấy text giờ (Stale)"
                        except Exception as e_get_text:
                            print(f"[{city}] Lỗi khi lấy text từ panel giờ chi tiết: {e_get_text}")
                            opening_hours = "Lỗi lấy text giờ chi tiết"

                    # Final check: If hours still holds the initial default message, update based on outcome
                    elif opening_hours == "Không lấy được giờ từ GMap":
                        if not clicked and hours_trigger_element is None:
                            opening_hours = "Không tìm thấy/click được thông tin giờ trên GMap" # No trigger found
                        elif not clicked and hours_trigger_element is not None:
                             opening_hours = "Lỗi click nút giờ (tất cả selectors thất bại)" # Trigger found but click failed
                        # If click succeeded but panel didn't appear, message is already set in the wait block

                except Exception as e_hours_main:
                     # Catch any unexpected error in the main hours block
                     print(f"[{city}] Lỗi không xác định khi xử lý giờ mở cửa từ GMap: {e_hours_main}")
                     print(traceback.format_exc())
                     # Ensure a final error state if something unexpected happened
                     if opening_hours == "Không lấy được giờ từ GMap": # If not set by inner errors
                          opening_hours = "Lỗi xử lý giờ GMap (ngoài)"


                # --- Append Data ---
                city_data.append({
                    "Thành phố": city,
                    "Tên công ty": name,
                    "Địa chỉ": address,
                    "Số điện thoại": phone_number,
                    "Website": domain_name,          # Use extracted domain name
                    "Giờ hoạt động": opening_hours, # Use hours extracted from GMap
                    "Google Maps URL": original_gmaps_url, # Store original Gmaps link
                    "Vĩ độ": lat,                   # Use extracted latitude
                    "Kinh độ": lng,                   # Use extracted longitude
                    # "Full Website URL": website_url_full # Optional: Uncomment to keep full URL
                })
                # Print summary, showing first line of hours for brevity
                hours_summary = ' '.join(opening_hours.splitlines()[:1]) if isinstance(opening_hours, str) else opening_hours
                print(f"[{city}] -> Đã thêm: {name} (Website: {domain_name}, Lat: {lat}, Lng: {lng}, Hours: {hours_summary}...)")


            except Exception as e_proc:
                # Catch major errors during the processing of a single result
                print(f"[{city}] !!! LỖI NGHIÊM TRỌNG khi xử lý KQ {i + 1} ({res_info.get('aria_label', 'N/A')}) !!!")
                print(traceback.format_exc())
                # Append error record to keep track
                city_data.append({
                    "Thành phố": city,
                    "Tên công ty": res_info.get('aria_label', f"Lỗi xử lý KQ {i+1}"),
                    "Địa chỉ": "Lỗi xử lý",
                    "Số điện thoại": "Lỗi xử lý",
                    "Website": "Lỗi xử lý",
                    "Giờ hoạt động": "Lỗi xử lý", # Indicate error state
                    "Google Maps URL": original_gmaps_url, # Store URL even on error
                    "Vĩ độ": "",   # Ensure empty on error
                    "Kinh độ": ""   # Ensure empty on error
                })
            finally:
                # IMPORTANT: Navigate away after processing each detail page
                # This helps prevent JavaScript state from one page interfering with the next
                print(f"[{city}] Điều hướng về Google Search để chuẩn bị cho mục tiếp theo...")
                try:
                    # Go to a simple, known page like a blank search
                    driver.get("https://www.google.com/search?q=next")
                    # Wait briefly for the search input box to appear, confirming navigation
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q")))
                    time.sleep(0.5) # Short extra pause
                except Exception as e_nav_back:
                     print(f"[{city}] CẢNH BÁO: Không thể điều hướng về google search: {e_nav_back}. Thử làm mới.")
                     try:
                         driver.refresh() # Try refreshing current page as a fallback
                         time.sleep(2)
                     except Exception as e_refresh:
                          print(f"[{city}] CẢNH BÁO: Làm mới trang cũng thất bại: {e_refresh}")
                          # Continue anyway, the next loop iteration will call driver.get() for the Gmaps link

        # --- End of loop processing results for one city ---
        print(f"--- Hoàn thành thu thập cho: {city} ---")
        return city_data

    except Exception as e_main:
         # Catch critical errors in the main function for a city (e.g., driver init, search failure)
         print(f"[{city}] !!! LỖI NGHIÊM TRỌNG TRONG scrape_city !!!")
         print(traceback.format_exc())
         return [] # Return empty list on major failure for this city
    finally:
        # Ensure the browser is closed even if errors occurred
        if driver:
            try:
                driver.quit()
                print(f"[{city}] Đã đóng trình duyệt.")
            except Exception as e_quit:
                print(f"[{city}] Lỗi khi đóng trình duyệt: {e_quit}")

# --- Main Execution Block ---
start_time = time.time()
all_data = [] # List to store data from all cities
print("=== BẮT ĐẦU QUÁ TRÌNH SCRAPE ===")

# Loop through each city defined in the list
for city in cities:
    city_start_time = time.time()
    try:
        # Call the scraping function for the current city
        city_data = scrape_city(city)
        # Check if data was returned (i.e., no critical error occurred)
        if city_data:
            all_data.extend(city_data) # Add the city's data to the main list
            print(f"[{city}] Đã thêm {len(city_data)} kết quả vào danh sách tổng.")
        else:
            print(f"[{city}] Không có dữ liệu trả về từ scrape_city (có thể do lỗi nghiêm trọng hoặc không có kết quả).")
    except Exception as e_city_run:
         # Catch unexpected errors during the function call itself
         print(f"!!! LỖI KHÔNG XỬ LÝ ĐƯỢC khi chạy scrape_city cho {city} !!!")
         print(traceback.format_exc())

    city_end_time = time.time()
    print(f"=== Hoàn thành {city} trong {city_end_time - city_start_time:.2f} giây ===")

    # Optional: Pause between cities
    if city != cities[-1]: # Don't pause after the last city
        pause_duration = 5
        print(f"--- Tạm nghỉ {pause_duration} giây trước khi xử lý thành phố tiếp theo ---")
        time.sleep(pause_duration)

# --- Export Results ---
if all_data:
    print(f"\nTổng cộng thu thập được {len(all_data)} kết quả từ {len(cities)} thành phố.")
    print("Đang chuẩn bị xuất file Excel...")
    # Create DataFrame from the collected data
    df = pd.DataFrame(all_data)

    # Define the desired output file name
    output_file = "tat_ca_kho_tu_quan_Australia_gmap_hours_coords_final_v3.xlsx" # Added v3

    try:
        # Define the desired column order for the output file
        columns_order = [
            "Thành phố", "Tên công ty", "Địa chỉ", "Số điện thoại", "Website",
            "Giờ hoạt động", "Google Maps URL", "Vĩ độ", "Kinh độ",
            # Optional: "Full Website URL" # Uncomment if you added this column
        ]
        # Ensure all expected columns exist in the DataFrame, add if missing with empty string
        for col in columns_order:
            if col not in df.columns:
                df[col] = "" # Use empty string as default for missing columns

        # Reindex the DataFrame to enforce the desired column order and include any added columns
        df = df.reindex(columns=columns_order)

        # --- Optional Data Cleaning ---
        # Clean up phone numbers (remove extra spaces, etc.)
        if "Số điện thoại" in df.columns:
            df["Số điện thoại"] = df["Số điện thoại"].astype(str).str.replace(r'\s{2,}', ' ', regex=True).str.strip()
            # Replace common error messages with empty string or N/A if preferred
            phone_errors = ["Không lấy được SĐT", "Lỗi regex SĐT từ Aria", "Container không có text/href/aria hợp lệ",
                            "Lỗi href SĐT generic", "Không tìm thấy SĐT (Timeout)", "Lỗi không xác định khi lấy SĐT", "Lỗi xử lý"]
            df["Số điện thoại"] = df["Số điện thoại"].replace(phone_errors, 'N/A')

        # Clean up Website (Domain) column
        if "Website" in df.columns:
             website_errors = ["Lỗi phân tích URL", "Lỗi tìm trang web", "Không có trang web (URL không hợp lệ)", "Lỗi xử lý", "Chưa kiểm tra"]
             df["Website"] = df["Website"].replace(website_errors, 'Không có trang web')


        # Clean up Lat/Lng columns (replace placeholders/errors)
        coord_errors = ["Không tìm thấy", "Lỗi tọa độ", "Lỗi xử lý", ""]
        df['Vĩ độ'] = df['Vĩ độ'].replace(coord_errors, 'N/A').fillna('N/A')
        df['Kinh độ'] = df['Kinh độ'].replace(coord_errors, 'N/A').fillna('N/A')

        # Clean up Hours column (standardize error messages)
        if "Giờ hoạt động" in df.columns:
            hours_errors = [ "Không lấy được giờ từ GMap", "Không mở được panel giờ chi tiết sau khi nhấp",
                             "Lỗi chờ panel giờ chi tiết", "Không tìm thấy thông tin giờ ban đầu trên GMap",
                             "Panel giờ chi tiết trống", "Lỗi lấy text giờ (Stale)", "Lỗi lấy text giờ chi tiết",
                             "Lỗi xử lý giờ GMap (ngoài)", "Không tìm thấy/click được thông tin giờ trên GMap",
                             "Lỗi click nút giờ (tất cả selectors thất bại)", "Lỗi xử lý"]
            df["Giờ hoạt động"] = df["Giờ hoạt động"].replace(hours_errors, 'Không có thông tin giờ')
            df["Giờ hoạt động"] = df["Giờ hoạt động"].astype(str).str.strip() # Ensure trimming


        # Attempt to save to Excel
        df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\n🎉 Đã lưu xong toàn bộ dữ liệu vào file '{output_file}'!")

    except ImportError:
         # Handle case where openpyxl is not installed
         print("\n🚨 Lỗi: Thư viện 'openpyxl' chưa được cài đặt.")
         print("   Vui lòng chạy: pip install openpyxl")
         print("Đang thử lưu sang định dạng CSV thay thế...")
         output_file_csv = "tat_ca_kho_tu_quan_Australia_gmap_hours_coords_final_v3.csv" # Added v3
         try:
             # Ensure correct column order for CSV backup as well
             if all(col in df.columns for col in columns_order):
                 df_csv = df[columns_order] # Select columns in order
             else:
                 df_csv = df # Use DataFrame as is if reindex failed somehow
             # Save to CSV with UTF-8 encoding (with BOM for Excel compatibility)
             df_csv.to_csv(output_file_csv, index=False, encoding='utf-8-sig')
             print(f"\n⚠️ Đã lưu tạm thời vào file CSV '{output_file_csv}'.")
         except Exception as e_csv:
            print(f"\n🚨 Lỗi nghiêm trọng khi lưu file CSV thay thế: {e_csv}")

    except Exception as e_excel:
        # Handle other potential errors during Excel export
        print(f"\n🚨 Lỗi khi lưu file Excel '{output_file}': {e_excel}")
        print(traceback.format_exc()) # Print detailed Excel error
        print("Đang thử lưu sang định dạng CSV thay thế...")
        output_file_csv = "tat_ca_kho_tu_quan_Australia_gmap_hours_coords_final_v3.csv" # Added v3
        try:
             # Ensure correct column order for CSV backup
             if all(col in df.columns for col in columns_order):
                 df_csv = df[columns_order]
             else:
                 df_csv = df
             df_csv.to_csv(output_file_csv, index=False, encoding='utf-8-sig')
             print(f"\n⚠️ Đã lưu tạm thời vào file CSV '{output_file_csv}' do lỗi Excel.")
        except Exception as e_csv_fallback:
            print(f"\n🚨 Lỗi nghiêm trọng khi lưu file CSV thay thế (sau lỗi Excel): {e_csv_fallback}")
else:
    # Message if no data was collected from any city
    print("\n🤷 Không thu thập được dữ liệu nào từ bất kỳ thành phố nào.")

# --- Final Timing ---
end_time = time.time()
total_duration = end_time - start_time
print(f"\n=== HOÀN THÀNH TOÀN BỘ QUÁ TRÌNH TRONG {total_duration:.2f} giây ({total_duration/60:.2f} phút) ===")