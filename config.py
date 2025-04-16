# gmaps_scraper_project/config.py

# -*- coding: utf-8 -*-

# --- Configuration Variables ---

# List of major cities in Australia
CITIES = [
    "Sydney",
    # "Melbourne",
    # "Brisbane",
    # "Perth",
    # "Adelaide"
    # Add more cities if needed
]

USER_AGENT_LIST = [
    # Existing
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36 Edg/115.0.1901.183',

    # New
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.62 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.187 Safari/537.36',
    'Mozilla/5.0 (iPad; CPU OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.216 Mobile Safari/537.36'
]


# Default output filename
DEFAULT_OUTPUT_FILENAME = "gmaps_self_storage_data.xlsx"

# Scraping limits (optional)
MAX_RESULTS_TO_COLLECT_PER_CITY = 200
MAX_RESULTS_TO_PROCESS_PER_CITY = 200
MAX_SCROLL_ATTEMPTS = 15

# Debug log filename
DEBUG_LOG_FILENAME = 'gmaps_scraper_debug.log'