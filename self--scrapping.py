# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
from urllib.parse import urlparse, parse_qs, urlsplit # <<< IMPORT THIS and others needed
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
    options.add_argument("--lang=en-US")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = None
    try:
        # Khởi tạo WebDriver
        # Use context manager for driver installation if preferred
        # with ChromeDriverManager().install() as driver_path:
        #     service = Service(driver_path)
        #     driver = webdriver.Chrome(service=service, options=options)
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

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
            consent_locator = (By.XPATH, "//button[.//span[contains(text(), 'Accept all') or contains(text(), 'Agree') or contains(text(), 'Reject all')]] | //button[@aria-label='Accept all' or @aria-label='Agree' or @aria-label='Reject all'] | //button[contains(@jsname, 'b3VHJd')] | //form[contains(@action, 'consent')]//button")
            consent_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(consent_locator))
            # Try clicking directly first
            try:
                consent_button.click()
            except ElementClickInterceptedException:
                 print(f"[{city}] Click trực tiếp bị chặn, thử dùng Javascript...")
                 driver.execute_script("arguments[0].click();", consent_button)
            print(f"[{city}] Đã xử lý cookies/consent.")
            time.sleep(2)
        except TimeoutException:
            print(f"[{city}] Không tìm thấy nút consent hoặc không cần thiết.")
        except Exception as e:
            print(f"[{city}] Lỗi khi xử lý consent: {e}")
            print(traceback.format_exc()) # Print stack trace for consent errors

        # --- Search ---
        try:
            search_box = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "searchboxinput")))
            search_box.clear()
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.ENTER)
            print(f"[{city}] Đã tìm kiếm: {search_query}")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/maps/place/')]"))
            )
            print(f"[{city}] Kết quả tìm kiếm đã bắt đầu xuất hiện.")
            time.sleep(5) # Allow results list to populate initially
        except Exception as e_search:
            print(f"[{city}] Lỗi nghiêm trọng khi thực hiện tìm kiếm: {e_search}")
            raise

        # --- Scroll ---
        scroll_attempts = 0
        max_scroll_attempts = 7 # Increased scroll attempts for potentially longer lists
        feed_scroll_selector = "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]/parent::div"
        try:
            feed_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, feed_scroll_selector))
            )
            print(f"[{city}] Bắt đầu scroll panel kết quả...")
            last_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
            no_change_count = 0
            end_of_list_xpath = "//span[contains(text(), \"You've reached the end of the list.\")]"

            while scroll_attempts < max_scroll_attempts:
                # Check if 'You've reached the end of the list.' is visible
                try:
                     end_element = driver.find_element(By.XPATH, end_of_list_xpath)
                     if end_element.is_displayed():
                         print(f"[{city}] Phát hiện thông báo cuối danh sách. Dừng scroll.")
                         break
                except NoSuchElementException:
                    pass # Keep scrolling if not found

                # Scroll down using JS, targeting the specific feed element
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", feed_element)
                time.sleep(3.5) # Wait for content to load - adjust if needed

                # Calculate new scroll height and compare with last scroll height
                new_height = driver.execute_script("return arguments[0].scrollHeight", feed_element)
                results_count_after_scroll = len(driver.find_elements(By.XPATH, "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]/div/div//a[contains(@href, '/maps/place/') and @aria-label]"))
                print(f"[{city}] Đã scroll lần {scroll_attempts + 1}. Chiều cao mới: {new_height}. Số kết quả hiện tại: {results_count_after_scroll}")

                if new_height == last_height:
                    no_change_count += 1
                    print(f"[{city}] Chiều cao không đổi (lần {no_change_count}).")
                    # Check for end-of-list message again after height check
                    try:
                         end_element = driver.find_element(By.XPATH, end_of_list_xpath)
                         if end_element.is_displayed():
                             print(f"[{city}] Chiều cao không đổi VÀ thấy thông báo cuối danh sách. Dừng scroll.")
                             break
                    except NoSuchElementException:
                        pass
                    # If height hasn't changed for a few attempts, assume end or error
                    if no_change_count >= 3: # Increase threshold slightly
                        print(f"[{city}] Chiều cao không đổi {no_change_count} lần liên tiếp. Dừng scroll.")
                        break
                else:
                    no_change_count = 0 # Reset counter if height changed
                    last_height = new_height

                scroll_attempts += 1

            if scroll_attempts == max_scroll_attempts:
                 print(f"[{city}] Đạt số lần scroll tối đa ({max_scroll_attempts}).")

        except TimeoutException:
            print(f"[{city}] Không tìm thấy panel kết quả để scroll ({feed_scroll_selector}).")
        except Exception as e:
             print(f"[{city}] Lỗi khi scroll: {e}")
             print(traceback.format_exc())


        # --- Get Result Links ---
        # Adjusted XPath to be more specific to result items, avoiding nested links within ads sometimes
        results_xpath = "//div[contains(@aria-label, 'Results for') or contains(@aria-label, 'Kết quả cho')]/div/div[.//a[contains(@href, '/maps/place/')]]/a[@aria-label and contains(@href, '/maps/place/')]"
        result_links = []
        processed_links = set()
        MAX_RESULTS = 20 # Set your desired limit
        try:
            WebDriverWait(driver, 10).until( # Increased wait after scroll
                EC.presence_of_element_located((By.XPATH, results_xpath))
            )
            potential_results = driver.find_elements(By.XPATH, results_xpath)
            print(f"[{city}] Tìm thấy {len(potential_results)} thẻ 'a' tiềm năng trong panel kết quả (dùng XPath đã chỉnh).")
            for res in potential_results:
                 try:
                     href = res.get_attribute('href')
                     aria_label = res.get_attribute('aria-label')
                     # Basic validation
                     if href and href.startswith("https://www.google.com/maps/place/") and aria_label and href not in processed_links:
                         result_links.append({'href': href, 'aria_label': aria_label})
                         processed_links.add(href)
                         if len(result_links) >= MAX_RESULTS:
                             print(f"[{city}] Đã đạt giới hạn MAX_RESULTS ({MAX_RESULTS}).")
                             break
                 except StaleElementReferenceException:
                     print(f"[{city}] Bỏ qua phần tử link bị stale.")
                     continue
                 except Exception as e_link_attr:
                     print(f"[{city}] Lỗi khi lấy thuộc tính link: {e_link_attr}")
                     continue
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

        for i, res_info in enumerate(result_links):
            if i >= MAX_RESULTS: break
            print(f"\n[{city}] === Đang xử lý Kết quả {i + 1}/{min(len(result_links), MAX_RESULTS)} ===")
            original_gmaps_url = res_info.get('href', 'Lỗi lấy URL') # Store the original Gmaps link
            print(f"[{city}] Tên (từ link): {res_info.get('aria_label', 'N/A')}")
            print(f"[{city}] URL Gmaps gốc: {original_gmaps_url}")

            # --- Initialize data fields ---
            name = res_info.get('aria_label', "Lỗi lấy tên")
            address = "Lỗi lấy địa chỉ"
            phone_number = "Lỗi lấy SĐT"
            website_url_full = "Không có trang web"
            domain_name = "Không có trang web"
            opening_hours = "Chưa kiểm tra trang web"
            lat, lng = "", "" # Initialize Lat/Lng

            try:
                # --- Navigate to Google Maps Detail Page ---
                print(f"[{city}] Đang điều hướng tới: {original_gmaps_url}")
                driver.get(original_gmaps_url)
                detail_page_url = "" # Initialize detail page URL
                try:
                     # Wait for H1 or the main content area to be somewhat loaded
                     WebDriverWait(driver, 15).until(
                         EC.any_of(
                             EC.visibility_of_element_located((By.TAG_NAME, "h1")),
                             EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']")) # A common wrapper for main content
                         )
                     )
                     print(f"[{city}] Trang chi tiết Gmaps đã tải (thấy H1 hoặc main content).")
                     # <<< IMPORTANT: Get CURRENT URL after waiting >>>
                     time.sleep(1) # Small pause just in case URL updates slightly after EC condition met
                     detail_page_url = driver.current_url
                     print(f"[{city}] URL hiện tại sau khi tải: {detail_page_url}")

                except TimeoutException:
                     print(f"[{city}] CẢNH BÁO: Trang chi tiết Gmaps tải chậm hoặc không có H1/main content trong 15s.")
                     # Still try to get the current URL even if wait failed
                     detail_page_url = driver.current_url
                     print(f"[{city}] URL hiện tại (sau timeout): {detail_page_url}")
                     time.sleep(5) # Give more time if elements not immediately visible

                # --- Extract Lat/Lng (Prioritize current URL) ---
                lat, lng = "", ""
                coords_found = False
                try:
                    url_to_check_primary = detail_page_url if detail_page_url else original_gmaps_url # Use current if available
                    print(f"[{city}] Đang kiểm tra tọa độ trong URL: {url_to_check_primary}")

                    # --- Try extracting from PRIMARY URL (@ format) ---
                    url_pattern = re.compile(r'@(-?\d+\.\d+),(-?\d+\.\d+)')
                    coords_match = url_pattern.search(url_to_check_primary)
                    if coords_match:
                        lat = coords_match.group(1)
                        lng = coords_match.group(2)
                        print(f"[{city}] Đã trích xuất tọa độ từ URL (@): Lat {lat}, Lng {lng}")
                        coords_found = True
                    else:
                        # --- Try extracting from PRIMARY URL (data= format) ---
                        data_pattern = re.compile(r'data=.*?(!3d|%213d)(-?\d+\.\d+).*?(!4d|%214d)(-?\d+\.\d+)') # Handle encoding ! = %21
                        data_match = data_pattern.search(url_to_check_primary)
                        if data_match:
                            # Groups depend on which separator was matched (!3d or %213d)
                            lat = data_match.group(2) # Latitude value is always group 2
                            lng = data_match.group(4) # Longitude value is always group 4
                            print(f"[{city}] Đã trích xuất tọa độ từ URL (data=): Lat {lat}, Lng {lng}")
                            coords_found = True

                    # --- If not found in PRIMARY, try the OTHER URL as fallback ---
                    if not coords_found and detail_page_url and original_gmaps_url != detail_page_url:
                        url_to_check_secondary = original_gmaps_url
                        print(f"[{city}] Không tìm thấy trong URL chính, thử URL gốc: {url_to_check_secondary}")
                        coords_match = url_pattern.search(url_to_check_secondary) # Check original URL (@)
                        if coords_match:
                            lat = coords_match.group(1)
                            lng = coords_match.group(2)
                            print(f"[{city}] Đã trích xuất tọa độ từ URL GỐC (@): Lat {lat}, Lng {lng}")
                            coords_found = True
                        else:
                            data_match = data_pattern.search(url_to_check_secondary) # Check original URL (data=)
                            if data_match:
                                lat = data_match.group(2)
                                lng = data_match.group(4)
                                print(f"[{city}] Đã trích xuất tọa độ từ URL GỐC (data=): Lat {lat}, Lng {lng}")
                                coords_found = True

                    # --- If STILL not found, try the JavaScript fallback ---
                    # (Keep the JS fallback as it was, it's a last resort)
                    if not coords_found:
                        print(f"[{city}] Không tìm thấy tọa độ trong URL, thử fallback JavaScript...")
                        try:
                            # Wait for the map to load and execute JavaScript to get coordinates
                            time.sleep(2)  # Give maps time to initialize
                            location_script = """
                                var loc = document.querySelector('meta[property="og:image"]');
                                if (loc) {
                                    var imgSrc = loc.getAttribute('content');
                                    var match = imgSrc.match(/center=([^&]+)/);
                                    return match ? match[1] : null;
                                }
                                // Fallback: Try finding script tag with lat/lng (more fragile)
                                const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                                for (const script of scripts) {
                                    try {
                                        const data = JSON.parse(script.textContent);
                                        if (data && data.geo && data.geo.latitude && data.geo.longitude) {
                                            return data.geo.latitude + ',' + data.geo.longitude;
                                        }
                                        // Look for other potential structures if needed
                                    } catch (e) {}
                                }
                                return null;
                            """
                            center_param = driver.execute_script(location_script)

                            if center_param and ',' in center_param:
                                coords = center_param.split(',')
                                if len(coords) >= 2:
                                    lat_cand = coords[0].strip()
                                    lng_cand = coords[1].strip()
                                    # Basic validation for lat/lng values
                                    if re.match(r'^-?\d+\.\d+$', lat_cand) and re.match(r'^-?\d+\.\d+$', lng_cand):
                                        lat = lat_cand
                                        lng = lng_cand
                                        print(f"[{city}] Đã trích xuất tọa độ từ page source (JS fallback): Lat {lat}, Lng {lng}")
                                        coords_found = True
                                    else:
                                         print(f"[{city}] Giá trị JS fallback không hợp lệ: {center_param}")
                                else:
                                    print(f"[{city}] Không thể phân tích tọa độ từ center_param (JS fallback): {center_param}")
                            else:
                                print(f"[{city}] Không tìm thấy tọa độ qua JS fallback (meta/script).")
                        except Exception as e_coords_js:
                            print(f"[{city}] Lỗi khi cố gắng lấy tọa độ từ page (JS fallback): {e_coords_js}")

                    if not coords_found:
                        print(f"[{city}] CẢNH BÁO: Không thể trích xuất tọa độ bằng mọi phương pháp.")
                        lat, lng = "", "" # Ensure they are empty strings if not found

                except Exception as e_coords:
                    lat, lng = "", ""
                    print(f"[{city}] Lỗi chung khi trích xuất tọa độ: {e_coords}")
                    print(traceback.format_exc())

                # --- Get Name (từ H1) ---
                # (Giữ nguyên logic lấy Tên, Địa chỉ, SĐT, Website, Giờ hoạt động)
                # ... (Your existing code for Name, Address, Phone, Website, Hours) ...
                # --- Get Name (từ H1) ---
                try:
                    name_element = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.TAG_NAME, "h1"))
                        )
                    fetched_name = name_element.text.strip()
                    if fetched_name: name = fetched_name
                    print(f"[{city}] Tên (H1): {name}")
                except TimeoutException:
                     print(f"[{city}] Không tìm thấy H1 trong 5s. Giữ tên từ aria-label.")
                except NoSuchElementException:
                     print(f"[{city}] Không tìm thấy H1. Giữ tên từ aria-label.")
                except Exception as e_name:
                     print(f"[{city}] Lỗi khi lấy tên từ H1: {e_name}.")

                # --- Get Address ---
                address = "Không lấy được địa chỉ"
                try:
                    # Prioritize button with specific data-item-id
                    address_locator = (By.CSS_SELECTOR, "button[data-item-id='address'] div.Io6YTe, button[data-item-id='address'] div.QsDR1c")
                    address_element = WebDriverWait(driver, 7).until(EC.visibility_of_element_located(address_locator))
                    address = address_element.text.strip()
                    print(f"[{city}] Địa chỉ (Button data-item-id): {address}")
                except TimeoutException:
                     print(f"[{city}] Không tìm thấy địa chỉ bằng button data-item-id. Thử tìm div chung hơn...")
                     try:
                         # Fallback to a div likely containing the address text near the icon
                         # Looking for a div that contains text like St, Rd, NSW, etc. and is near the pin icon element
                         address_alt_locator = (By.XPATH, "//button[contains(@aria-label, 'Address') or contains(@data-tooltip, 'Address')]/following-sibling::div[contains(@class, 'Io6YTe') or contains(@class, 'QsDR1c')] | //div[contains(@class,'Io6YTe')][string-length(text()) > 5 and (contains(., ' St') or contains(., ' Rd') or contains(., ' Ave') or contains(., ' NSW') or contains(., ' VIC') or contains(., ' QLD'))]")
                         address_elements = WebDriverWait(driver, 5).until(EC.visibility_of_all_elements_located(address_alt_locator))
                         if address_elements:
                            # Select the most likely candidate (e.g., the first visible one with substantial text)
                            for el in address_elements:
                                addr_text = el.text.strip()
                                if addr_text and len(addr_text) > 10: # Simple check for reasonable length
                                    address = addr_text
                                    print(f"[{city}] Địa chỉ (Fallback Div): {address}")
                                    break
                            if address == "Không lấy được địa chỉ": # If loop finished without finding suitable text
                                print(f"[{city}] Địa chỉ fallback tìm thấy div nhưng text không phù hợp.")
                         else:
                             print(f"[{city}] Địa chỉ fallback không tìm thấy div phù hợp.")

                     except Exception as e_addr_fallback:
                          print(f"[{city}] Lấy địa chỉ fallback thất bại: {e_addr_fallback}")
                except Exception as e_addr:
                     print(f"[{city}] Lỗi khác khi lấy địa chỉ: {e_addr}")
                     print(traceback.format_exc())

                # --- Get Phone Number ---
                phone_number = "Không lấy được SĐT"
                try:
                    # Prioritize elements with data-item-id hinting phone number
                    phone_container_locator = (By.CSS_SELECTOR, "a[data-item-id^='phone:tel:'], button[data-item-id^='phone:tel:']")
                    phone_container_element = WebDriverWait(driver, 7).until(EC.presence_of_element_located(phone_container_locator))

                    # Try finding the visible text first (often inside a div)
                    try:
                        phone_text_element = phone_container_element.find_element(By.CSS_SELECTOR, "div.Io6YTe, div.QsDR1c")
                        pn_text = phone_text_element.text.strip()
                        if pn_text and re.search(r'[\d\+() ]{7,}', pn_text): # Check for digits, +, (), space, min length 7
                             phone_number = pn_text
                             print(f"[{city}] SĐT (Text inside container): {phone_number}")
                        else:
                            # If text is not phone-like, try other attributes
                            raise NoSuchElementException
                    except NoSuchElementException:
                        # If no inner text or not phone-like, check attributes of the container
                        aria_label = phone_container_element.get_attribute('aria-label')
                        href = phone_container_element.get_attribute('href') if phone_container_element.tag_name == 'a' else None

                        if href and href.startswith('tel:'):
                            phone_number = href.replace('tel:', '').strip()
                            print(f"[{city}] SĐT (Href): {phone_number}")
                        elif aria_label:
                            # Try extracting from aria-label (e.g., "Phone: +61 2...")
                            match = re.search(r'(\+?\s?[\d\s()-]{8,})', aria_label) # Look for at least 8 digits/spaces/etc.
                            if match:
                                phone_number = match.group(1).strip()
                                print(f"[{city}] SĐT (Aria): {phone_number}")
                            else:
                                phone_number = "Lỗi regex SĐT từ Aria"
                        else:
                            phone_number = "Container không có text/href/aria hợp lệ"

                except TimeoutException:
                    print(f"[{city}] Không tìm thấy container SĐT chuẩn (data-item-id). Thử tìm link tel bất kỳ...")
                    try:
                        # Fallback: Find any link starting with 'tel:'
                        generic_phone_link = WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='tel:']")))
                        href = generic_phone_link.get_attribute('href')
                        if href and href.startswith('tel:'):
                            phone_number = href.replace('tel:', '').strip()
                            print(f"[{city}] SĐT (Generic Href): {phone_number}")
                        else: phone_number = "Lỗi href SĐT generic"
                    except TimeoutException:
                         print(f"[{city}] Không tìm thấy link SĐT nào.")
                         phone_number = "Không tìm thấy SĐT (Timeout)"
                except Exception as e_phone:
                    print(f"[{city}] Lỗi không xác định khi lấy SĐT: {e_phone}")
                    print(traceback.format_exc())
                    phone_number = "Lỗi không xác định khi lấy SĐT"


                # --- Get Website URL from Google Maps ---
                website_url_full = "Không có trang web"
                domain_name = "Không có trang web"
                try:
                    # Prioritize specific data-item-id or aria-label for website
                    website_selectors = [
                        "a[data-item-id='authority'][href^='http']",      # Often the primary website link
                        "a[aria-label*='Website:'][href^='http']",        # Aria label starting with "Website:"
                        "button[aria-label*='Website:']",                # Sometimes it's a button that reveals link
                        "a[href*='://'][data-tooltip*='website' i]",      # Tooltip contains "website" (case-insensitive)
                        "a[href*='://'][aria-label*='website' i]",       # Aria label contains "website"
                    ]
                    found_url = None
                    for selector in website_selectors:
                        try:
                             elements = driver.find_elements(By.CSS_SELECTOR, selector)
                             for element in elements:
                                # Skip hidden elements unless it's the only option found later
                                # if not element.is_displayed() and found_url: continue

                                href = element.get_attribute('href')
                                # If it's a button, sometimes the website is in data-url or needs click (handle later if needed)
                                if not href and element.tag_name == 'button':
                                     # Placeholder for potentially clicking button later if needed
                                     pass # print(f"[{city}] Found button for website, might need click: {element.get_attribute('aria-label')}")

                                if href and href.startswith('http'):
                                    # Basic check to avoid obvious map/search links if possible
                                    parsed_temp = urlparse(href)
                                    # Allow google redirects for now, handle later
                                    # if 'google.com' not in parsed_temp.netloc and 'google.com.au' not in parsed_temp.netloc:
                                    found_url = href
                                    print(f"[{city}] Tìm thấy URL tiềm năng (Selector: {selector}): {found_url}")
                                    # Prioritize non-google redirect links if found
                                    if '/url?q=' not in found_url:
                                        break # Found a direct link, likely the best
                                    # else keep checking for a potentially better direct link

                             if found_url and '/url?q=' not in found_url: # Stop if direct link found
                                 break
                        except Exception as e_sel:
                             print(f"[{city}] Lỗi nhỏ khi kiểm tra selector '{selector}': {e_sel}")
                             continue # Try next selector

                    # If still no URL or only google redirect found, try generic link near website icon
                    if not found_url or '/url?q=' in found_url:
                         try:
                             # Look for a link immediately following the "Website" icon/button
                             generic_website_link = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Website')]//ancestor::div[position()=1]//following-sibling::div//a[@href^='http'] | //img[contains(@aria-label, 'Website')]//ancestor::div[position()=1]//following-sibling::div//a[@href^='http']")
                             generic_href = generic_website_link.get_attribute('href')
                             if generic_href and generic_href.startswith('http'):
                                 # Prefer this generic link if it's not a google redirect, otherwise keep the existing found_url
                                 if '/url?q=' not in generic_href:
                                      print(f"[{city}] Tìm thấy trang web (Generic Fallback near icon, direct): {generic_href}")
                                      found_url = generic_href
                                 elif not found_url: # Only use generic google redirect if nothing else was found
                                      print(f"[{city}] Tìm thấy trang web (Generic Fallback near icon, redirect): {generic_href}")
                                      found_url = generic_href

                         except NoSuchElementException:
                             print(f"[{city}] Không tìm thấy link generic gần icon website.")
                         except Exception as e_gen:
                             print(f"[{city}] Lỗi khi thử generic fallback cho website: {e_gen}")


                    # --- Process the found URL ---
                    if found_url:
                         # Handle Google URL redirects if necessary
                         if '/url?q=' in found_url:
                              try:
                                   # from urllib.parse import parse_qs, urlsplit # Already imported
                                   query_params = parse_qs(urlsplit(found_url).query)
                                   if 'q' in query_params and query_params['q']:
                                       website_url_full = query_params['q'][0]
                                       print(f"[{city}] Trích xuất URL thực từ Google redirect: {website_url_full}")
                                   else:
                                       website_url_full = found_url # Use redirect URL if extraction fails
                                       print(f"[{city}] Giữ lại URL redirect (không trích xuất được q): {website_url_full}")
                              except Exception as e_redirect:
                                   print(f"[{city}] Lỗi khi xử lý Google redirect URL: {e_redirect}")
                                   website_url_full = found_url # Fallback to using the redirect URL itself
                         else:
                              website_url_full = found_url # It's a direct URL
                              print(f"[{city}] Trang web trực tiếp: {website_url_full}")

                         # <<< START DOMAIN EXTRACTION >>>
                         if website_url_full and website_url_full.startswith('http'):
                             try:
                                 parsed_uri = urlparse(website_url_full)
                                 # Normalize: remove www. and potential trailing slash
                                 netloc = parsed_uri.netloc.lower()
                                 if netloc.startswith('www.'):
                                     domain_name = netloc[4:]
                                 else:
                                     domain_name = netloc
                                 domain_name = domain_name.rstrip('/')
                                 print(f"[{city}] Trích xuất tên miền: {domain_name}")
                             except Exception as e_parse:
                                 print(f"[{city}] Lỗi khi phân tích URL trang web thành tên miền: {e_parse}")
                                 domain_name = "Lỗi phân tích URL"
                         # <<< END DOMAIN EXTRACTION >>>
                    else:
                         print(f"[{city}] Không tìm thấy link trang web trên Google Maps sau các lần thử.")
                         website_url_full = "Không có trang web"
                         domain_name = "Không có trang web"

                except Exception as e_website_find:
                    print(f"[{city}] Lỗi khi tìm link trang web trên Google Maps: {e_website_find}")
                    print(traceback.format_exc())
                    website_url_full = "Lỗi tìm trang web"
                    domain_name = "Lỗi tìm trang web"

                # --- Scrape Opening Hours from Website (if found) ---
                opening_hours = "Chưa kiểm tra trang web" # Reset before check
                if domain_name not in ["Không có trang web", "Lỗi tìm trang web", "Lỗi phân tích URL"]:
                    print(f"[{city}] Đang điều hướng tới trang web: {website_url_full}")
                    try:
                        # Navigate with timeout handling
                        driver.set_page_load_timeout(25) # Set timeout for page load
                        try:
                             driver.get(website_url_full)
                        except TimeoutException:
                            print(f"[{city}] Lỗi: Trang web tải quá lâu (page load timeout > 25s). Dừng xử lý trang web.")
                            try:
                                driver.execute_script("window.stop();") # Attempt to stop loading
                            except WebDriverException as e_stop:
                                print(f"[{city}] Lỗi khi cố gắng dừng tải trang: {e_stop}")
                            opening_hours = "Lỗi tải trang web (Timeout)"
                            # Skip further processing of this site by raising an exception that the outer block catches
                            # raise TimeoutException("Page load timeout")
                            # Or just set the opening_hours and let it continue to append data
                        except WebDriverException as e_nav_web:
                             # Catch navigation errors like DNS resolution, connection refused etc.
                             print(f"[{city}] Lỗi WebDriver khi truy cập trang web '{website_url_full}': {e_nav_web}")
                             if 'net::ERR_NAME_NOT_RESOLVED' in str(e_nav_web):
                                 opening_hours = "Lỗi tải trang web (Không tìm thấy tên miền)"
                             elif 'net::ERR_CONNECTION_REFUSED' in str(e_nav_web):
                                  opening_hours = "Lỗi tải trang web (Kết nối bị từ chối)"
                             elif 'net::ERR_CONNECTION_TIMED_OUT' in str(e_nav_web):
                                 opening_hours = "Lỗi tải trang web (Hết thời gian chờ kết nối)"
                             elif 'net::ERR_ABORTED' in str(e_nav_web):
                                 opening_hours = "Lỗi tải trang web (Tải bị hủy)"
                             else:
                                  opening_hours = f"Lỗi tải trang web (WebDriver)"
                             # Skip further processing for this site if navigation failed severely
                             # raise WebDriverException("Web navigation failed")


                        # If navigation didn't raise a fatal error, proceed
                        if opening_hours == "Chưa kiểm tra trang web": # Check if navigation succeeded/wasn't fatal
                            # Wait for body after potentially long load or partial load
                            try:
                                body_element = WebDriverWait(driver, 10).until(
                                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                                )
                                print(f"[{city}] Đã tải trang web (ít nhất là body). Đang lấy nội dung...")
                                time.sleep(3) # Increased pause for JS rendering
                                body_text = body_element.text.lower() # Get text content

                                if not body_text or len(body_text) < 50: # Check if body text is meaningful
                                    print(f"[{city}] CẢNH BÁO: Nội dung body trang web trống hoặc quá ngắn. Thử innerHTML.")
                                    try:
                                        body_html = driver.page_source.lower() # Get full source as fallback
                                        # Very basic regex on HTML source - less reliable
                                        html_matches = re.findall(r'>([^<]*?(?:hour|open|close|trading|access|mon|tue|wed|thu|fri|sat|sun)[^<]*?)<', body_html, re.IGNORECASE)
                                        if html_matches:
                                            potential_hour_lines_html = [re.sub('<[^>]+>', '', m).strip() for m in html_matches if len(m.strip()) > 3 and len(m.strip()) < 150]
                                            potential_hour_lines_html = [line for line in potential_hour_lines_html if re.search(r'\d', line) or 'closed' in line or '24 hour' in line] # Must contain number or closed/24h
                                            unique_lines = sorted(list(set(potential_hour_lines_html)), key=potential_hour_lines_html.index)
                                            if unique_lines:
                                                opening_hours = "\n".join(unique_lines[:8])
                                                if len(unique_lines) > 8: opening_hours += "\n[... more lines truncated]"
                                                print(f"[{city}] Thông tin giờ tiềm năng trích xuất từ HTML:\n{opening_hours}")
                                            else:
                                                opening_hours = "Nội dung trang web trống/ngắn (HTML không có giờ)"
                                        else:
                                            opening_hours = "Nội dung trang web trống/ngắn (Text và HTML)"
                                    except Exception as e_html:
                                         print(f"[{city}] Lỗi khi phân tích HTML trang web: {e_html}")
                                         opening_hours = "Nội dung trang web trống/ngắn (Lỗi phân tích HTML)"
                                else:
                                     print(f"[{city}] Tìm kiếm từ khóa giờ trong {len(body_text)} ký tự text...")
                                     # More focused regex for lines containing Day + Time or keywords
                                     potential_hour_lines = []
                                     lines = body_text.split('\n')
                                     # Keywords needing stricter context (e.g., require digits nearby)
                                     time_keywords = ['hour', 'open', 'close', 'trading', 'access', 'office', 'customer']
                                     day_keywords = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun', 'weekday', 'weekend', 'daily', 'everyday', 'public holiday']

                                     for line in lines:
                                         line_strip = line.strip()
                                         if len(line_strip) > 4 and len(line_strip) < 150: # Filter length
                                             line_lower = line_strip.lower()
                                             # Check for Day + Number/Range/Closed OR Time Keyword + Number/Range/Closed
                                             has_day = any(day_kw in line_lower for day_kw in day_keywords)
                                             has_time_num = re.search(r'\d{1,2}([:.]?\d{2})?\s*(am|pm)?', line_lower) # Match 9am, 5pm, 17:00 etc.
                                             has_range = re.search(r'[-–to]', line_lower) or 'closed' in line_lower or '24 hour' in line_lower or 'appointment' in line_lower
                                             has_keyword = any(kw in line_lower for kw in time_keywords)

                                             # Rule 1: Must have a number/range/closed/appointment indicator
                                             if not (has_time_num or has_range):
                                                  continue

                                             # Rule 2: Must have EITHER a day OR a relevant time keyword
                                             if not (has_day or has_keyword):
                                                  continue

                                             # Add if rules pass and not already added
                                             if line_strip not in potential_hour_lines:
                                                 potential_hour_lines.append(line_strip)


                                     if potential_hour_lines:
                                         # Further filter/clean potential lines (optional, depends on noise)
                                         # e.g., remove lines that are clearly just phone numbers mistaken for times
                                         filtered_lines = [l for l in potential_hour_lines if not re.fullmatch(r'[\d\s()+-]+', l)]

                                         unique_lines = sorted(list(set(filtered_lines)), key=filtered_lines.index) # Use filtered list
                                         opening_hours = "\n".join(unique_lines[:8]) # Limit lines stored
                                         if len(unique_lines) > 8:
                                             opening_hours += "\n[... more lines truncated]"
                                         print(f"[{city}] Thông tin giờ tiềm năng trích xuất từ text trang web:\n{opening_hours}")
                                     else:
                                        # Check if *any* keyword was present even if no specific line matched
                                        keyword_found_in_text = any(kw in body_text for kw in time_keywords + day_keywords)
                                        if keyword_found_in_text:
                                             opening_hours = "Tìm thấy từ khóa giờ nhưng không trích xuất được dòng cụ thể"
                                        else:
                                             opening_hours = "Không tìm thấy từ khóa/mẫu giờ trên trang web"

                            except TimeoutException: # Catch timeout from WebDriverWait for body
                                 print(f"[{city}] Lỗi: Không tìm thấy thẻ 'body' trang web trong 10s.")
                                 opening_hours = "Lỗi tải trang web (Timeout phần tử body)"
                            except Exception as e_scrape_web_body:
                                print(f"[{city}] Lỗi không xác định khi lấy hoặc xử lý nội dung text/body trang web: {e_scrape_web_body}")
                                print(traceback.format_exc())
                                opening_hours = f"Lỗi xử lý nội dung trang web"

                    # except TimeoutException: # Already handled by specific try/except for driver.get
                    #     # Message printed above
                    #     pass
                    # except WebDriverException: # Already handled by specific try/except for driver.get
                    #      # Message printed above
                    #      pass
                    except Exception as e_scrape_web_outer:
                        print(f"[{city}] Lỗi không xác định bên ngoài khi xử lý trang web: {e_scrape_web_outer}")
                        print(traceback.format_exc())
                        if opening_hours == "Chưa kiểm tra trang web": # If not set by inner errors
                            opening_hours = f"Lỗi xử lý trang web (ngoài)"

                elif domain_name == "Không có trang web":
                    opening_hours = "Không có trang web để kiểm tra giờ"
                else: # Handle other error cases for domain_name like "Lỗi tìm trang web"
                     opening_hours = f"Không thể kiểm tra giờ ({domain_name})"


                # --- Append Data ---
                city_data.append({
                    "Thành phố": city,
                    "Tên công ty": name,
                    "Địa chỉ": address,
                    "Số điện thoại": phone_number,
                    "Website": domain_name,          # Domain name stored here
                    "Giờ hoạt động": opening_hours,
                    "Google Maps URL": original_gmaps_url, # Store the original Gmaps URL
                    "Vĩ độ": lat,                   # <<< Use the extracted lat
                    "Kinh độ": lng,                   # <<< Use the extracted lng
                    # "Full Website URL": website_url_full # Optional: Uncomment to keep full URL
                })
                print(f"[{city}] -> Đã thêm: {name} (Website: {domain_name}, Lat: {lat}, Lng: {lng})") # <<< Updated print

            except Exception as e_proc:
                print(f"[{city}] !!! LỖI NGHIÊM TRỌNG khi xử lý KQ {i + 1} ({res_info.get('aria_label', 'N/A')}) !!!")
                print(traceback.format_exc())
                city_data.append({
                    "Thành phố": city,
                    "Tên công ty": res_info.get('aria_label', f"Lỗi xử lý KQ {i+1}"),
                    "Địa chỉ": "Lỗi xử lý",
                    "Số điện thoại": "Lỗi xử lý",
                    "Website": "Lỗi xử lý",
                    "Giờ hoạt động": "Lỗi xử lý",
                    "Google Maps URL": original_gmaps_url, # Store original URL even on error
                    "Vĩ độ": "",   # <<< Ensure empty on error
                    "Kinh độ": ""   # <<< Ensure empty on error
                })
            finally:
                # IMPORTANT: Navigate away to prevent JS interference
                print(f"[{city}] Điều hướng về Google Search để chuẩn bị cho mục tiếp theo...")
                try:
                    # Go to a simple, known page
                    driver.get("https://www.google.com/search?q=next")
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "q"))) # Wait for search box
                    time.sleep(0.5) # Short extra pause
                except Exception as e_nav_back:
                     print(f"[{city}] CẢNH BÁO: Không thể điều hướng về google search: {e_nav_back}. Thử làm mới.")
                     try:
                         driver.refresh() # Try refreshing current page as fallback
                         time.sleep(2)
                     except Exception as e_refresh:
                          print(f"[{city}] CẢNH BÁO: Làm mới cũng thất bại: {e_refresh}")
                          # Continue anyway, next loop will call driver.get() again
                          pass


        print(f"--- Hoàn thành thu thập cho: {city} ---")
        return city_data

    except Exception as e_main:
         print(f"[{city}] !!! LỖI NGHIÊM TRỌNG TRONG scrape_city !!!")
         print(traceback.format_exc())
         return [] # Return empty list on major failure for this city
    finally:
        if driver:
            try:
                driver.quit()
                print(f"[{city}] Đã đóng trình duyệt.")
            except Exception as e_quit:
                print(f"[{city}] Lỗi khi đóng trình duyệt: {e_quit}")

# --- Main Execution ---
start_time = time.time()
all_data = []
print("=== BẮT ĐẦU QUÁ TRÌNH SCRAPE ===")
for city in cities:
    city_start_time = time.time()
    try:
        city_data = scrape_city(city)
        if city_data:
            all_data.extend(city_data)
            print(f"[{city}] Đã thêm {len(city_data)} kết quả vào danh sách tổng.")
        else:
            print(f"[{city}] Không có dữ liệu trả về từ scrape_city.")
    except Exception as e_city_run:
         print(f"!!! LỖI KHÔNG XỬ LÝ ĐƯỢC khi chạy scrape_city cho {city} !!!")
         print(traceback.format_exc())
    city_end_time = time.time()
    print(f"=== Hoàn thành {city} trong {city_end_time - city_start_time:.2f} giây ===")
    if city != cities[-1]:
        pause_duration = 5
        print(f"--- Tạm nghỉ {pause_duration} giây trước khi xử lý thành phố tiếp theo ---")
        time.sleep(pause_duration)

# --- Export ---
if all_data:
    print(f"\nTổng cộng thu thập được {len(all_data)} kết quả.")
    print("Đang chuẩn bị xuất file Excel...")
    df = pd.DataFrame(all_data)
    output_file = "tat_ca_kho_tu_quan_Australia_domain_hours_coords.xlsx" # Updated output name
    try:
        # Define the desired column order
        columns_order = [
            "Thành phố", "Tên công ty", "Địa chỉ", "Số điện thoại", "Website",
            "Giờ hoạt động", "Google Maps URL", "Vĩ độ", "Kinh độ", 
            # Optional: "Full Website URL"
        ]
        # Ensure all expected columns exist, add if missing with appropriate default
        for col in columns_order:
            if col not in df.columns:
                df[col] = "" # Use empty string or pd.NA as default

        df = df.reindex(columns=columns_order) # Reorder/select columns

        # Optional: Clean up phone numbers (remove extra spaces, etc.)
        if "Số điện thoại" in df.columns:
            df["Số điện thoại"] = df["Số điện thoại"].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()

        # Optional: Fill missing Lat/Lng with a placeholder if preferred over blank
        df['Vĩ độ'] = df['Vĩ độ'].fillna('N/A')
        df['Kinh độ'] = df['Kinh độ'].fillna('N/A')

        df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\n🎉 Đã lưu xong toàn bộ dữ liệu vào file '{output_file}'!")
    except ImportError:
         print("\n🚨 Lỗi: Thư viện 'openpyxl' chưa được cài đặt. Vui lòng chạy: pip install openpyxl")
         print("Đang thử lưu sang CSV...")
         output_file_csv = "tat_ca_kho_tu_quan_Australia_domain_hours_coords.csv"
         try:
             df.to_csv(output_file_csv, index=False, encoding='utf-8-sig')
             print(f"\n⚠️ Đã lưu tạm thời vào file CSV '{output_file_csv}'.")
         except Exception as e_csv:
            print(f"\n🚨 Lỗi khi lưu file CSV: {e_csv}")
    except Exception as e_excel:
        print(f"\n🚨 Lỗi khi lưu file Excel ({output_file}): {e_excel}")
        print(traceback.format_exc()) # Print detailed excel error
        output_file_csv = "tat_ca_kho_tu_quan_Australia_domain_hours_coords.csv"
        try:
            # Ensure correct column order for CSV too
            if all(col in df.columns for col in columns_order):
                 df = df[columns_order]
            df.to_csv(output_file_csv, index=False, encoding='utf-8-sig')
            print(f"\n⚠️ Đã lưu tạm thời vào file CSV '{output_file_csv}' do lỗi Excel.")
        except Exception as e_csv:
            print(f"\n🚨 Lỗi khi lưu file CSV thứ cấp: {e_csv}")
else:
    print("\n🤷 Không thu thập được dữ liệu nào từ bất kỳ thành phố nào.")

end_time = time.time()
total_duration = end_time - start_time
print(f"\n=== HOÀN THÀNH TOÀN BỘ QUÁ TRÌNH TRONG {total_duration:.2f} giây ({total_duration/60:.2f} phút) ===")