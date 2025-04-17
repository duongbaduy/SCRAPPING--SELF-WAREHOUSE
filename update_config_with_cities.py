import pandas as pd
import re
import os
from collections import defaultdict
import pprint # For cleaner printing of the dictionary structure

CONFIG_FILE = "config.py"
CSV_FILE = "resources/cities_au.csv"
# Let's increase TOP_N slightly if needed to ensure good coverage per state
# Or keep it and accept that smaller states might have fewer cities listed
TOP_N = 400

def get_australian_cities_by_region(csv_file, top_n):
    """
    Gets the top N Australian cities grouped by region (admin_name).

    Args:
        csv_file (str): Path to the CSV file.
        top_n (int): The total number of largest cities to consider overall.

    Returns:
        dict: A dictionary where keys are region names (str) and
              values are lists of city names (list[str]) within that region,
              sorted alphabetically within each region.
              Returns None if the CSV or required columns are missing.
    """
    if not os.path.exists(csv_file):
        print(f"❌ ERROR: CSV file not found at '{csv_file}'")
        return None

    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"❌ ERROR: Could not read CSV file '{csv_file}': {e}")
        return None

    # Check for required columns
    required_cols = ['city', 'country', 'admin_name']
    if not all(col in df.columns for col in required_cols):
        print(f"❌ ERROR: CSV file '{csv_file}' is missing one or more required columns: {required_cols}")
        return None

    # Filter for Australia and drop rows with missing city or admin_name
    df_aus = df[df['country'] == 'Australia'].dropna(subset=['city', 'admin_name']).copy() # Use .copy()

    if df_aus.empty:
        print("❌ ERROR: No Australian cities found in the CSV or required columns were empty.")
        return None

    # --- Determine sorting column ---
    sort_col = None
    if 'population_proper' in df_aus.columns and df_aus['population_proper'].notna().any():
         # Convert to numeric, coercing errors, then fill NaNs before sorting
         df_aus['population_sort'] = pd.to_numeric(df_aus['population_proper'], errors='coerce')
         sort_col = 'population_sort'
         print("ℹ️ Sorting by 'population_proper'.")
    elif 'population' in df_aus.columns and df_aus['population'].notna().any():
         df_aus['population_sort'] = pd.to_numeric(df_aus['population'], errors='coerce')
         sort_col = 'population_sort'
         print("ℹ️ Sorting by 'population'.")
    else:
        print("⚠️ WARNING: No 'population_proper' or 'population' column found for sorting. Using alphabetical order.")
        # No reliable population, sort by city name later if needed

    # --- Get Top N overall cities ---
    if sort_col:
        # Sort by population descending, handle potential NaN after coercion
        df_top_n = df_aus.sort_values(by=sort_col, ascending=False, na_position='last').head(top_n)
    else:
         # If no population data, just take the first N rows (order might be arbitrary)
         # Or sort alphabetically by city first to get a consistent subset
         df_top_n = df_aus.sort_values(by='city').head(top_n)


    # --- Group the Top N cities by region ---
    regions_cities = defaultdict(list)
    # Ensure we don't have duplicate city names *within the same region*
    grouped = df_top_n.groupby('admin_name')['city'].apply(lambda x: list(sorted(x.drop_duplicates()))).to_dict()

    # Convert defaultdict to regular dict for cleaner output/storage
    # And sort the regions alphabetically
    sorted_regions_cities = dict(sorted(grouped.items()))

    if not sorted_regions_cities:
         print("⚠️ WARNING: No cities were grouped. Check data and TOP_N.")
         return {} # Return empty dict

    print(f"✅ Successfully grouped {sum(len(c) for c in sorted_regions_cities.values())} cities into {len(sorted_regions_cities)} regions.")
    # print("\nRegions and Sample Cities:")
    # for region, cities in sorted_regions_cities.items():
    #     sample = cities[:3]
    #     print(f"  - {region}: {sample}{'...' if len(cities) > 3 else ''}")

    return sorted_regions_cities

def update_config_py(config_file, regions_data):
    """Updates the config file with the new REGIONS_AND_CITIES dictionary."""
    if regions_data is None:
        print("❌ ERROR: No region data provided to update config.")
        return
    if not isinstance(regions_data, dict):
        print("❌ ERROR: Invalid data type for regions_data (expected dict).")
        return

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"⚠️ WARNING: Config file '{config_file}' not found. Creating a new one.")
        content = "# -*- coding: utf-8 -*-\n\n# --- Configuration Variables ---\n\n"
    except Exception as e:
        print(f"❌ ERROR: Could not read config file '{config_file}': {e}")
        return

    # Format the dictionary string using pprint for readability
    new_region_block = f"REGIONS_AND_CITIES = {pprint.pformat(regions_data, indent=4)}\n"

    # Define the regex to find the old CITIES list or the new REGIONS_AND_CITIES dict
    # It looks for either 'CITIES = [...]' or 'REGIONS_AND_CITIES = {...}'
    # and replaces the whole block.
    pattern = r"^(CITIES\s*=\s*\[.*?\]|REGIONS_AND_CITIES\s*=\s*\{.*?\})\s*$"

    # Use re.MULTILINE and re.DOTALL
    # MULTILINE: ^ matches start of line, $ matches end of line
    # DOTALL: . matches newline
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        print(f"ℹ️ Found existing CITIES or REGIONS_AND_CITIES block. Replacing...")
        new_content = re.sub(
            pattern,
            new_region_block,
            content,
            count=1, # Replace only the first match
            flags=re.MULTILINE | re.DOTALL
        )
    else:
        print(f"ℹ️ No existing block found. Appending REGIONS_AND_CITIES...")
        # Append after '# --- Configuration Variables ---' if possible, otherwise at the end
        marker = "# --- Configuration Variables ---"
        if marker in content:
            new_content = content.replace(marker, f"{marker}\n\n{new_region_block}", 1)
        else:
            new_content = content + "\n" + new_region_block

    # --- Also remove the old CITIES list if it exists separately ---
    # This regex finds 'CITIES = [...]' potentially spanning multiple lines
    old_cities_pattern = r"^\s*CITIES\s*=\s*\[.*?\]\s*$"
    # Check if the pattern exists AND it's not the same as the block we just inserted
    # (This check is a bit redundant given the first replacement, but adds safety)
    if re.search(old_cities_pattern, new_content, re.MULTILINE | re.DOTALL) and old_cities_pattern not in new_region_block:
        print("ℹ️ Removing obsolete CITIES list.")
        new_content = re.sub(old_cities_pattern, "", new_content, count=1, flags=re.MULTILINE | re.DOTALL)


    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(new_content.strip() + "\n") # Ensure clean end of file
        print(f"✅ Updated '{config_file}' with {len(regions_data)} regions.")
    except Exception as e:
        print(f"❌ ERROR: Could not write to config file '{config_file}': {e}")


if __name__ == "__main__":
    # Ensure the resources directory exists relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, CSV_FILE)
    config_path = os.path.join(script_dir, CONFIG_FILE)


    regions_cities_data = get_australian_cities_by_region(csv_path, TOP_N)
    if regions_cities_data is not None: # Proceed only if data was loaded successfully
        update_config_py(config_path, regions_cities_data)
    else:
        print("❌ Update failed because city data could not be loaded/processed.")