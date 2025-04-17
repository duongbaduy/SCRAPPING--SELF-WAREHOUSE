from setuptools import setup

APP = ['main.py']  # Thay thế 'main.py' bằng file chính của ứng dụng bạn
DATA_FILES = ['install_driver.py']
OPTIONS = {
    'argv_emulation': False,
    'packages': [
        'tkinter', 
        'ttkbootstrap', 
        'pandas', 
        'selenium', 
        'webdriver_manager'
    ],
    'includes': [
        'gui', 
        'config',

        
    ],
    'excludes': ['matplotlib', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'],  # Loại bỏ các module không cần thiết
    'iconfile': 'assets/icon.icns',  # Tùy chọn: thêm icon cho ứng dụng (nếu có)
    # Selenium driver resources
    'resources': ['chromedriver'],  # Nếu bạn có file chromedriver cụ thể
    'plist': {
        'CFBundleName': 'Scraper Application',
        'CFBundleDisplayName': 'Scraper Application',
        'CFBundleIdentifier': 'com.dngbaduy.scraperapplication',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': '© 2025 DUONG BA DUY',
        # Các quyền cần thiết cho Selenium automation
        'NSAppleEventsUsageDescription': 'The application needs to automate web browsers for web scraping.',
        'NSCameraUsageDescription': 'This app does not use the camera.',
        'NSMicrophoneUsageDescription': 'This app does not use the microphone.'
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)