with open('install_driver.py', 'w') as f:
    f.write('''
# Script tự động cài đặt ChromeDriver
from webdriver_manager.chrome import ChromeDriverManager
driver_path = ChromeDriverManager().install()
print(f"ChromeDriver installed at: {driver_path}")
''')