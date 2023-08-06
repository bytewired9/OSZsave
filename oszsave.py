# Selenium is a web testing library used to automate browser activities.
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
# httpx is a fully featured HTTP client for Python 3, which provides sync and async APIs.
import httpx
# urllib.parse module is used for breaking Uniform Resource Locator (URL) string up in components (addressing scheme, network location, path etc.), 
# to combine the components back into a URL string, and to convert a “relative URL” to an absolute URL given a “base URL.”
from urllib import parse
# os module in Python provides functions for interacting with the operating system. It comes under Python’s standard utility modules.
import os
# time module in Python provides various time-related functions.
import time  
# unicodedata module provides access to the Unicode Character Database which defines character properties for all Unicode characters.
import unicodedata
# re module provides support for regular expressions in Python.
import re
# json module is used to work with JSON data.
import json
# random module is used to perform the random generations.
import random
# datetime module supplies classes to work with date and time. These classes provide a number of functions to deal with dates, times and time intervals.
from datetime import datetime
# shutil module in Python provides many functions of high-level operations on files and collections of files. It comes under Python’s standard utility modules.
import shutil

# --------------------------------------------------------------------------

# Function to scrape user profiles and collect download URLs
def scraper():

    # List to store URLs collected
    paydirt = []
    # Classes for elements of interest on the web page
    targets = ["play-detail__title", "beatmapset-panel__main-link", "profile-extra-entries__text", "beatmap-playcount__title"]

    # Check if the URL matches the expected pattern for osu.ppy.sh user profiles
    def is_valid_url(url):
        return re.match(r'https://osu\.ppy\.sh/users/\d+', url) is not None

    # Scroll to a specific section of the web page
    def scroll_to_section(driver, data_page_id):
        script = f"""
        var section = document.querySelector('[data-page-id="{data_page_id}"]');
        if (section) section.scrollIntoView({{ behavior: 'auto', block: 'center' }});
        """
        driver.execute_script(script)

    # Scroll to the bottom of the web page
    def scroll_to_bottom(driver):
        script = "window.scrollTo(0, document.body.scrollHeight);"
        driver.execute_script(script)
        time.sleep(1)  # Allow time for the content to load

    # Find 'next' buttons and click them to reveal more content
    def find_next_buttons(driver):
        scroll_to_bottom(driver)

    # For each section, scroll to it and click 'next' until there are no more 'next' buttons
    # Then move to the next section
        print("Searching for 'next' buttons...")
        sections_to_scroll = ["recent_activity", "top_ranks", "medals", "historical", "beatmaps"]
        sections_expanded = 0
        start_time = time.time()

        for section in sections_to_scroll:
            scroll_to_section(driver, section)
            time.sleep(1)  # Allow the section to load

            while True:
                try:
                    # Wait for the "next" button to be clickable
                    wait = WebDriverWait(driver, 2)  # Wait up to 2 seconds
                    btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".show-more-link--profile-page")))

                    driver.execute_script("arguments[0].scrollIntoView({ behavior: 'auto', block: 'center' });", btn)
                    btn.click()
                    time.sleep(1)  # Allow the page to load new content
                    sections_expanded += 1
                    elapsed_time = time.time() - start_time
                    print(f'\rExpanding link sections. [Sections expanded: {sections_expanded}; Time elapsed: {elapsed_time:.2f} seconds]', end='', flush=True)
                except TimeoutException:
                    print(f"\rNo more 'next' buttons found in the section '{section}'. Moving to the next section...")
                    break

        print("\nNo more 'next' buttons found, start digging gold!")
        dig_for_gold(driver)


    # Collect URLs from the web page
    def dig_for_gold(driver):
        print("Start collecting URLs...")

        targets = ["play-detail__title", "beatmapset-panel__main-link", "profile-extra-entries__text", "beatmap-playcount__title"]
        paydirt = []
        links_collected = 0
        start_time = time.time()

        target_selectors = ', '.join([f'.{target}' for target in targets])
        target_elements = driver.find_elements(By.CSS_SELECTOR, target_selectors)
        target_links = driver.find_elements(By.CSS_SELECTOR, ', '.join([f'a.{target}' for target in targets]))

        all_links = target_elements + target_links

        for link_element in all_links:
            new_url = link_element.get_attribute('href')

            if new_url and not any([ 
                paydirt.__contains__(new_url), 
                new_url.startswith("https://osu.ppy.sh/u"), 
                new_url.endswith("/discussion"), 
                "https://osu.ppy.sh/beatmapsets/discussions/" in new_url ]):

                link_element.location_once_scrolled_into_view
                paydirt.append(new_url)
                links_collected += 1
                elapsed_time = time.time() - start_time
                print(f'\rCollected links. [Links collected: {links_collected}; Time elapsed: {elapsed_time:.2f} seconds]', end='', flush=True)
                time.sleep(0.01)  # wait for a short moment to avoid being too fast

        print("\nEnd collecting URLs...")
        process_paydirt(paydirt)


    # Process collected URLs and save them to a JSON file
    def process_paydirt(paydirt):
        print("Gold digging completed, processing URLs...")
        paydirt_modified = []
        for url in paydirt:
            match = re.match(r'/b/([0-9]+)\?[A-Za-z]=[0-9]+', url)
            if match:
                paydirt_modified.append(f'https://osu.ppy.sh/beatmapsets/{match.group(1)}/download')
            elif re.match(r'https://osu\.ppy\.sh/beatmapsets/[0-9]+$', url):
                paydirt_modified.append(url + "/download")
            else:
                paydirt_modified.append(re.sub(r'#[A-Za-z]+/[0-9]+', '/download', url))

        unique_paydirt = list(set(paydirt_modified))
        formatted_json = json.dumps(unique_paydirt, indent=4)  # Format with 4-space indentation

        config_path = os.path.join(os.getcwd(), 'config')
        filename = os.path.join(config_path, 'beatmap_list.json')

        # Check if the directory exists, and create it if not
        if not os.path.exists(config_path):
            os.makedirs(config_path)

        with open(filename, 'w') as file:
            file.write(formatted_json)

        duplicates_removed = len(paydirt_modified) - len(unique_paydirt)
        print(f"Final processed list of URLs saved to {filename}. Total unique links: {len(unique_paydirt)}. Duplicates removed: {duplicates_removed}")
    
    # Get the user's profile URL
    url_of_the_profile_page = input("Please enter the URL of the profile page, or press Enter for custom URL list: ")

    # Validate the URL
    if not is_valid_url(url_of_the_profile_page):

        # If user skipped, proceed with rest of code.
        if len(url_of_the_profile_page) == 0:
            return None
        
        else:
            print("Invalid URL entered. Please make sure to enter a valid osu! profile URL. Exiting...")
            exit()

    # Set up the Chrome browser
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")

    try:
        # Navigate to the profile page
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url_of_the_profile_page)
    except Exception as e:
        print(f"An error occurred while navigating to the URL: {e}. Exiting...")
        exit()

    print("Script started...")
    # Start by finding and clicking 'next' buttons
    find_next_buttons(driver)
    # Close the browser when finished
    driver.quit()

# --------------------------------------------------------------------------

# Function to extract headers from a curl command string
def extract_headers(curl_command):

    headers = {}  # Dictionary to store headers

    # Regular expression match to find all headers in the curl command
    matches = re.findall(r"-H '(.*?)'", curl_command)  

    for match in matches:  # For each header found
        key, value = match.split(": ", 1)  # Split it into a key-value pair
        headers[key] = value  # And store it in the headers dictionary
    return headers  # Return the headers dictionary

# --------------------------------------------------------------------------

# Function to get headers from a curl command saved in a .txt file
def get_headers():

    # Path where the curl command and headers will be stored
    config_path = os.path.join(os.getcwd(), 'config') 

    # Input file path
    input_filename = os.path.join(config_path, 'curl_command.txt')

    # Output file path
    output_filename = os.path.join(config_path, 'headers.json')

    # Create config folder if not exists
    os.makedirs(config_path, exist_ok=True)

    # Check if curl_command.txt exists or is empty
    if not os.path.exists(input_filename) or os.path.getsize(input_filename) == 0:
        with open(input_filename, 'w') as file:
            print("Please enter the curl command in", input_filename)
            print('Press Enter to Exit')
            input()
            exit()

    # Open the input file and read the curl command
    with open(input_filename, "r") as file:
        curl_command = file.read()

    # Extract the headers from the curl command
    headers = extract_headers(curl_command)

    # Try to open the output file and read the existing headers
    try:
        with open(output_filename, "r") as file:
            existing_headers = json.load(file)

           # If the headers were extracted successfully and differ from the existing headers,
           # save them to the output file
            if existing_headers and existing_headers == headers:
                print("Headers are already in the proper state.")
                return headers
    except FileNotFoundError:
        pass

    # Check if headers are empty
    if not headers:
        print("Extracted headers are empty. Please check the curl command in", input_filename)
        print('Press Enter to Exit')
        input()
        exit()

    with open(output_filename, "w") as file:
        json.dump(headers, file)
        print(f"Headers saved to {output_filename}.")

    # Return the headers dictionary
    return headers

# --------------------------------------------------------------------------

# Function to get URLs from a JSON file
def get_urls(filename=None):

    # Path to the configuration folder
    config_path = os.path.join(os.getcwd(), 'config')
    if filename is None:

        # If filename is not provided, use 'beatmap_list.json' as a default
        filename = os.path.join(config_path, 'beatmap_list.json')

    # Create config folder if not exists
    os.makedirs(config_path, exist_ok=True)

    # Create beatmap_list.json if not exists
    if not os.path.exists(filename):
        with open(filename, 'w') as file:
            print(f"Please enter the URLs in {filename}")
            json.dump([], file)
            print('Press Enter to Exit')
            input()
            exit()

    # Open the file and load the URLs
    with open(filename, "r") as fp:
        urls = json.load(fp)

        # Check if the list of URLs is empty
        if not urls:
            print(f"The {filename} file is empty.")
            print('Press Enter to Exit')
            input()
            exit()

        # Return the list of URLs
        return urls
    
# --------------------------------------------------------------------------

# Function to check if a specific item has been processed
def check_done(chk):
    filename = os.path.join(os.path.dirname(__file__), '..', 'config', 'done.json')

     # If the file doesn't exist, create it and initialize it with an empty list
    if not os.path.exists(filename):
        with open(filename, 'w') as file:
            file.write("[]")

    # Open the file and load the processed items
    with open(filename, "r") as fp:
        done = json.loads(fp.read())

        # Check if the item is in the list and return the result
        return bool(chk in done)

# --------------------------------------------------------------------------

# Function to sanitize a filename
def sanitize(filename):
  
  # List of characters that aren't allowed in filenames
  blacklist = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0"]

  # List of reserved words that aren't allowed as filenames
  reserved = [
      "CON",
      "PRN",
      "AUX",
      "NUL",
      "COM1",
      "COM2",
      "COM3",
      "COM4",
      "COM5",
      "COM6",
      "COM7",
      "COM8",
      "COM9",
      "LPT1",
      "LPT2",
      "LPT3",
      "LPT4",
      "LPT5",
      "LPT6",
      "LPT7",
      "LPT8",
      "LPT9",
  ]
  # Remove characters from blacklist
  filename = "".join(c for c in filename if c not in blacklist)

  # Remove control characters
  filename = "".join(c for c in filename if 31 < ord(c))

  # Normalize unicode characters
  filename = unicodedata.normalize("NFKD", filename)

  # Remove trailing periods and spaces
  filename = filename.rstrip(". ")
  filename = filename.strip()
  # Special handling for filenames with only periods
  if all([x == "." for x in filename]):
    filename = "__" + filename

  # Special handling for reserved filenames  
  if filename in reserved:
    filename = "__" + filename

  # Fallback for empty filenames
  if len(filename) == 0:
    filename = "__"
  if len(filename) > 255:
    parts = re.split(r"/|\\", filename)[-1].split(".")
    if len(parts) > 1:
      ext = "." + parts.pop()
      filename = filename[:-len(ext)]
    else:
      ext = ""
    if filename == "":
      filename = "__"

     # Shorten filenames longer than 255 characters
    if len(ext) > 254:
      ext = ext[254:]
    maxl = 255 - len(ext)
    filename = filename[:maxl]
    filename = filename + ext
    filename = filename.rstrip(". ")
    if len(filename) == 0:
      filename = "__"
  return filename

# --------------------------------------------------------------------------

 # Function to download file from given url.
def download_from_url(url):
    if url is None:
        print("URL is None, skipping download.")
        return None
    # Parse the query string in the URL to get the filename
    qs = parse.parse_qs(url)
    # Define the directory where the file will be downloaded
    download_path = os.path.join(os.getcwd(), 'downloaded')
    # If the directory does not exist, create it
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    # Sanitize the filename and join it with the download path
    filename = os.path.join(download_path, sanitize(qs[list(qs.keys())[0]][0]))
    # Open the file and write the content from the URL into it
    with open(filename, "wb") as fp, httpx.stream("GET", url, headers=headers, timeout=None) as r:
        for data in r.iter_bytes():
            fp.write(data)
    return filename

# --------------------------------------------------------------------------

# Function to check if a particular task is done
def check_done(chk):
    # It checks from a json file called 'done.json'
    filename = os.path.join(os.getcwd(), 'config', 'done.json')
    # If the file does not exist, create it and write an empty json array
    if not os.path.exists(filename):
        with open(filename, "w") as fp:
            fp.write(json.dumps([]))
    # Open the file and load the json array
    with open(filename, "r") as fp:
        done = json.loads(fp.read())
    # Check if the task is in the list of completed tasks
    # Return True if completed, else False
    return bool(chk in done)

# --------------------------------------------------------------------------

def mark_done(mrk):
    # The file where the completed tasks are stored
    filename = os.path.join(os.getcwd(), 'config', 'done.json')
    current = None
    # If the file does not exist, create it and write an empty json array
    if not os.path.exists(filename):
        with open(filename, "w") as fp:
            fp.write(json.dumps([]))
    # Open the file and load the json array into the variable "current"
    with open(filename, "r") as fp:
        current = json.loads(fp.read())
    # If the task is not in the list of completed tasks, add it
    if mrk not in current:
        current.append(mrk)
        # Write the updated list of completed tasks back into the file
        with open(filename, "w") as fp:
            fp.write(json.dumps(current))

# --------------------------------------------------------------------------

def get_download_url(url, successive_429s=0, last_reset_time=None, requests_since_reset=0):
    
    # If more than 200 requests have been made within an hour, wait until the next reset
    if last_reset_time and requests_since_reset >= 200:
        time_to_next_reset = 3600 - (time.time() - last_reset_time)
        print(f"Reached rate limit for this hour. Sleeping for {time_to_next_reset} seconds...")
        time.sleep(time_to_next_reset)
        last_reset_time = time.time()
        requests_since_reset = 0

    # Send a GET request to the provided URL
    response = httpx.get(url, headers=headers, timeout=None)

    # If the server responded with status code 429 (Too Many Requests),
    # wait for a specified time then recursively try to get the download URL again.
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 30)) * (2 ** successive_429s)
        print(f"Encountered 429 Too Many Requests, sleeping for {retry_after} seconds")
        time.sleep(retry_after)
        return get_download_url(url, successive_429s + 1, last_reset_time, requests_since_reset)
    
    # If the server responds with a 404 (Not Found) status code, skip the URL
    if response.status_code == 404:
        print(f"URL {url} returned 404, skipping.")
        mark_done(url)
        return None, last_reset_time, requests_since_reset
    
    # If the server responds with a 504 (Gateway Timeout) status code,
    # wait for 1 second then recursively try to get the download URL again.
    if response.status_code == 504:
        print("Encountered 504 Gateway Timeout, trying again in 1 second...")
        time.sleep(1)
        return get_download_url(url, successive_429s, last_reset_time, requests_since_reset)
    
    # If the server responds with any status code other than 302 (Found), print an error message
    elif response.status_code != 302:
        print(f"Download URL request returned code {response.status_code} instead of 302")
        return response.reason_phrase
    
    # If the response is 302 (Found), retrieve the redirect location from the headers
    download_location = response.headers.get('location')

    # Ensure the download location is valid
    if not download_location.startswith("https://"):
        raise ValueError(f"The Gods gave us a bad download location! {download_location}")


    # If there was a 429 response during this download attempt,
    # reset the start time for the rate limit and the request counter
    if successive_429s > 0: # If there was a 429 response during this download attempt
        last_reset_time = time.time() # Reset the start time for the rate limit
        requests_since_reset = 0 # Reset the request counter

    return download_location, last_reset_time, requests_since_reset + 1


# --------------------------------------------------------------------------

def find_osu_folder():
    # Define the default osu! installation folder path
    path = 'C:/users/{}/appdata/local/osu!'.format(os.getlogin())

    # Check if osu! folder exists in the default location
    if os.path.exists(path):
        return path
    else:
        # If it doesn't, print an error message and return None
        print("osu! folder not found. Please move the beatmaps manually.")
        return None

# --------------------------------------------------------------------------    
    
def move_files_confirmation(destination_folder):

    # If the destination folder doesn't exist, don't do anything
    if destination_folder is None:
        return
    
    # Create the songs folder if it doesn't already exist
    songs_folder = os.path.join(destination_folder, "Songs")
    os.makedirs(songs_folder, exist_ok=True)

    # Define the source folder (where the beatmaps are downloaded to)
    source_folder = os.path.join(os.path.dirname(__file__), 'downloaded')

    # Get user confirmation before moving the files
    confirmation = input(f"Do you want to move all beatmaps to {songs_folder}? (y/n): ")
    if confirmation.lower() != 'y':
        print("The beatmaps have been left in the download folder.")
        return
    
    # Move all the .osz files from the source to the songs folder
    for filename in os.listdir(source_folder):
        if filename.endswith(".osz"):
            shutil.move(os.path.join(source_folder, filename), songs_folder)

    # Print a success message
    print(f"All files moved to {songs_folder}")

# --------------------------------------------------------------------------

if __name__ == "__main__":
    # Starts the scraper
    scraper()

    # Sets up the headers
    headers = get_headers()

    # Gets a list of urls from a file
    urls = get_urls()

    # Initialize the request rate limit trackers
    last_reset_time = None
    requests_since_reset = 0

    # If there are no urls, end the script
    if not urls:
        print("No URLs found.")
        print("Press Enter to exit.")
        input()
        exit()

    # Initialize the count of processed urls
    processed_count = 0
    for i, each in enumerate(urls, 1):
        # If the url has already been processed, skip to the next
        if check_done(each):
            processed_count += 1
            continue

        # Download the beatmap
        current_time = datetime.now().strftime("%I:%M %p")
        print(f"\n\n[{i}] Downloading {each} at {current_time} ...")
        download_url, last_reset_time, requests_since_reset = get_download_url(each, last_reset_time=last_reset_time, requests_since_reset=requests_since_reset)

        # Write the downloaded beatmap to a file
        downloaded_filename = download_from_url(download_url)
        if downloaded_filename is None:
            continue
        mark_done(each)
        processed_count += 1
        print(f"Done with {os.path.basename(downloaded_filename)}!")

        # Wait a bit before making the next request
        sleep_duration = random.randint(5, 10)
        print(f"Sleeping for {sleep_duration} seconds before the next request...")
        time.sleep(sleep_duration)

    # If all urls have been processed, move the beatmaps to the osu! songs folder
    if processed_count == len(urls): 
        print("All URLs have been processed. Done.")
        osu_folder = find_osu_folder()
        move_files_confirmation(osu_folder)