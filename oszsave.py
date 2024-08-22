import os
import re
import time
import json
import httpx
import shutil
import unicodedata
from datetime import datetime
from urllib.parse import unquote, urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from colorama import init
import signal
try:
    import curses
except ImportError:
    if os.name == 'nt':
        import windows_curses as curses
    else:
        raise
# Initialize colorama
init(autoreset=True)

# Set a flag to indicate if the process should stop
stop_flag = False

# Signal handler for stopping the process
def signal_handler(sig, frame):
    global stop_flag
    stop_flag = True

signal.signal(signal.SIGINT, signal_handler)

CURRENT_VERSION = "1.4.0"

banner = """
  ██████╗ ███████╗███████╗███████╗ █████╗ ██╗   ██╗███████╗
 ██╔═══██╗██╔════╝╚══███╔╝██╔════╝██╔══██╗██║   ██║██╔════╝
 ██║   ██║███████╗  ███╔╝ ███████╗███████║██║   ██║█████╗  
 ██║   ██║╚════██║ ███╔╝  ╚════██║██╔══██║╚██╗ ██╔╝██╔══╝  
 ╚██████╔╝███████║███████╗███████║██║  ██║ ╚████╔╝ ███████╗
  ╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝
 ██████████████████████████████████████████████████████████╗
 ╚═════════════════════════════════════════════════════════╝
"""

def is_valid_url(url):
    """Check if the URL is valid."""
    return re.match(r'https://osu\.ppy\.sh/users/\d+', url) is not None

def scroll_to_section(driver, data_page_id):
    """Scroll to a specific section in the page."""
    script = f"""
    var section = document.querySelector('[data-page-id="{data_page_id}"]');
    if (section) section.scrollIntoView({{ behavior: 'auto', block: 'center' }});
    """
    driver.execute_script(script)

def scroll_to_bottom(driver):
    """Scroll to the bottom of the page."""
    script = "window.scrollTo(0, document.body.scrollHeight);"
    driver.execute_script(script)
    time.sleep(1)

def find_next_buttons(driver, stdscr):
    """Find and click 'next' buttons in different sections."""
    scroll_to_bottom(driver)
    add_str_to_curses(stdscr, "Searching for 'next' buttons...\n")
    sections_to_scroll = ["recent_activity", "top_ranks", "medals", "historical", "beatmaps"]
    sections_expanded = 0
    start_time = time.time()

    for section in sections_to_scroll:
        scroll_to_section(driver, section)
        time.sleep(1)
        while True:
            try:
                wait = WebDriverWait(driver, 2)
                btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".show-more-link--profile-page")))
                driver.execute_script("arguments[0].scrollIntoView({ behavior: 'auto', block: 'center' });", btn)
                btn.click()
                time.sleep(1)
                sections_expanded += 1
                elapsed_time = time.time() - start_time
                add_str_to_curses(stdscr, f'\rExpanding link sections. [Sections expanded: {sections_expanded}; Time elapsed: {elapsed_time:.2f} seconds]')
            except TimeoutException:
                add_str_to_curses(stdscr, f"\nNo more 'next' buttons found in the section '{section}'. Moving to the next section...\n")
                break

    add_str_to_curses(stdscr, "\nNo more 'next' buttons found, start digging gold!\n")
    dig_for_gold(driver, stdscr)

def dig_for_gold(driver, stdscr):
    """Collect URLs from the page."""
    add_str_to_curses(stdscr, "Start collecting URLs...\n")
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
            new_url in paydirt,
            new_url.startswith("https://osu.ppy.sh/u"),
            new_url.endswith("/discussion"),
            "https://osu.ppy.sh/beatmapsets/discussions/" in new_url
        ]):
            paydirt.append(new_url)
            links_collected += 1
            elapsed_time = time.time() - start_time
            add_str_to_curses(stdscr, f'\rCollected links. [Links collected: {links_collected}; Time elapsed: {elapsed_time:.2f} seconds]')
            time.sleep(0.01)

    add_str_to_curses(stdscr, "\nEnd collecting URLs...\n")
    process_paydirt(paydirt, stdscr)

def process_paydirt(paydirt, stdscr):
    """Process and save collected URLs to a file."""
    add_str_to_curses(stdscr, "Gold digging completed, processing URLs...\n")
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
    formatted_json = json.dumps(unique_paydirt, indent=4)

    filename = os.path.join(os.getcwd(), 'beatmap_list.json')

    with open(filename, 'w', encoding="utf_8") as file:
        file.write(formatted_json)

    duplicates_removed = len(paydirt_modified) - len(unique_paydirt)
    add_str_to_curses(stdscr, f"Final processed list of URLs saved to {filename}. Total unique links: {len(unique_paydirt)}. Duplicates removed: {duplicates_removed}\n")

def scraper(stdscr):
    """Main function to initiate the scraping process."""
    add_str_to_curses(stdscr, "Please enter the URL of the profile page, or press Enter for custom URL list: ")
    curses.echo()
    url_of_the_profile_page = stdscr.getstr().decode("utf-8")
    curses.noecho()

    if not is_valid_url(url_of_the_profile_page):
        if len(url_of_the_profile_page) == 0:
            return None
        else:
            add_str_to_curses(stdscr, "Invalid URL entered. Please make sure to enter a valid osu! profile URL. Exiting...\n")
            time.sleep(5)
            exit()

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url_of_the_profile_page)
    except Exception as e:
        add_str_to_curses(stdscr, f"An error occurred while navigating to the URL: {e}. Exiting...\n")
        time.sleep(5)
        exit()

    add_str_to_curses(stdscr, "Script started...\n")
    find_next_buttons(driver, stdscr)
    driver.quit()

def get_urls(stdscr, filename=None):
    """Retrieve URLs from the JSON file."""
    if filename is None:
        filename = os.path.join(os.getcwd(), 'beatmap_list.json')

    if not os.path.exists(filename):
        with open(filename, 'w', encoding="utf_8") as file:
            file.write("[]")
        add_str_to_curses(stdscr, f"Please enter the URLs in {filename}\n")
        add_str_to_curses(stdscr, 'Press Enter to Exit\n')
        stdscr.getkey()
        exit()

    with open(filename, "r", encoding="utf_8") as fp:
        urls = json.load(fp)
        if not urls:
            add_str_to_curses(stdscr, f"The {filename} file is empty.\n")
            add_str_to_curses(stdscr, 'Press Enter to Exit\n')
            stdscr.getkey()
            exit()

        return urls

def check_done(chk):
    """Check if the URL has already been processed."""
    filename = os.path.join(os.getcwd(), 'done.json')

    if not os.path.exists(filename):
        with open(filename, 'w', encoding="utf_8") as file:
            file.write("[]")

    with open(filename, "r", encoding="utf_8") as fp:
        done = json.loads(fp.read())
        return bool(chk in done)

def sanitize(filename):
    """Sanitize the filename to remove any invalid characters."""
    blacklist = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0"]
    reserved = [
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
        "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3",
        "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    ]

    filename = "".join(c for c in filename if c not in blacklist)
    filename = "".join(c for c in filename if 31 < ord(c))
    filename = unicodedata.normalize("NFKD", filename)
    filename = filename.rstrip(". ").strip()

    if all([x == "." for x in filename]):
        filename = "__" + filename

    if filename in reserved:
        filename = "__" + filename

    if len(filename) == 0:
        filename = "__"

    if len(filename) > 255:
        parts = re.split(r"/|\\", filename)[-1].split(".")
        ext = "." + parts.pop() if len(parts) > 1 else ""
        filename = filename[:-len(ext)]
        ext = ext[254:] if len(ext) > 254 else ext
        maxl = 255 - len(ext)
        filename = filename[:maxl] + ext
        filename = filename.rstrip(". ")
        if len(filename) == 0:
            filename = "__"

    return filename

def display_progress_bar(stdscr, progress, total, filename):
    """Display the progress bar for file download."""
    progress_percentage = progress / total * 100 if total > 0 else 0
    bar_length = 50  # Length of the progress bar
    filled_length = int(bar_length * progress / total) if total > 0 else 0

    bar = '#' * filled_length + '-' * (bar_length - filled_length)
    message = f'{filename[:30]:30} |{bar}| {progress_percentage:.2f}%'
    try:
        stdscr.addstr(17, 0, message)
        stdscr.clrtoeol()  # Clear the rest of the line to avoid leftover text
        stdscr.refresh()
    except curses.error:
        pass

def display_banner(stdscr, current, total, start_time):
    """Display the banner with current processing status."""
    elapsed_time = time.time() - start_time
    elapsed_minutes, elapsed_seconds = divmod(elapsed_time, 60)
    average_time = elapsed_time / current if current > 0 else 0
    estimated_time_left = average_time * (total - current)
    eta_minutes, eta_seconds = divmod(estimated_time_left, 60)

    banner_info = (
        f"Processing {current}/{total} | "
        f"Elapsed Time: {int(elapsed_minutes):02}:{int(elapsed_seconds):02} | "
        f"ETA: {int(eta_minutes):02}:{int(eta_seconds):02}"
    )

    cancel_notif = "Press 'x' to cancel"

    try:
        term_width = curses.COLS
        stdscr.addstr(10, 0, " " * term_width, curses.color_pair(1))
        stdscr.addstr(11, 0, "  " + banner_info.ljust(term_width - 2), curses.color_pair(1))
        stdscr.addstr(12, 0, "  " + cancel_notif.ljust(term_width - 2), curses.color_pair(1))
        stdscr.addstr(13, 0, " " * term_width, curses.color_pair(1))
        stdscr.refresh()
    except curses.error:
        pass

def download_from_url(url, stdscr, current, total, start_time):
    """Download file from the provided URL."""
    if url is None:
        add_str_to_curses(stdscr, "URL is None, skipping download.\n")
        return None

    pattern = r'https://osu\.ppy\.sh/beatmapsets/(\d+)'
    level_id = re.search(pattern, url).group(1)

    sources = [
        f'https://catboy.best/d/{level_id}',
        f'https://beatconnect.io/b/{level_id}/'
    ]

    for source_url in sources:
        add_str_to_curses(stdscr, f"Trying: {source_url}\n")

        try:
            with httpx.stream("GET", source_url, timeout=10) as r:
                if r.status_code == 301:
                    source_url = r.headers.get('location')
                    if source_url.startswith('/'):
                        source_url = urljoin('https://catboy.best', source_url)
                    add_str_to_curses(stdscr, f"Redirecting to: {source_url}\n")
                    r = httpx.get(source_url, timeout=10)

                if r.status_code != 200:
                    add_str_to_curses(stdscr, f"Failed with status code {r.status_code}. Trying next source...\n")
                    continue

                cd = r.headers.get('content-disposition')
                try:
                    encoded_filename = re.findall("filename=(.+)", cd)[0]
                    filename = unquote(encoded_filename)
                except Exception:
                    filename = 'default_filename.osz'

                sanitized_filename = sanitize(filename)

                download_path = os.path.join(os.getcwd(), 'downloaded')
                os.makedirs(download_path, exist_ok=True)
                full_path = os.path.join(download_path, sanitized_filename)

                total_bytes = int(r.headers.get("content-length", 0))
                progress = 0

                with open(full_path, "wb") as fp:
                    for data in r.iter_bytes():
                        # Check for stop flag before processing each chunk
                        if stop_flag:
                            add_str_to_curses(stdscr, "Stopping download...\n")
                            return None

                        progress += len(data)
                        fp.write(data)
                        display_progress_bar(stdscr, progress, total_bytes, sanitized_filename)

                return full_path
        except httpx.RequestError as e:
            add_str_to_curses(stdscr, f"Request error: {e}. Trying next source...\n")
        except httpx.TimeoutException:
            add_str_to_curses(stdscr, "Hm. This is taking a while, let's try a different one.\n")

    add_str_to_curses(stdscr, "All sources failed. Moving to the next URL.\n")
    return None

def main(stdscr):
    """Main function to start the application."""
    global stop_flag
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)

    clear_console(stdscr)
    stdscr.addstr(0, 0, banner, curses.color_pair(2))
    stdscr.refresh()

    check_for_updates(stdscr)

    scraper(stdscr)
    urls = get_urls(stdscr)

    last_reset_time = None
    requests_since_reset = 0

    if not urls:
        add_str_to_curses(stdscr, "No URLs found.\n")
        add_str_to_curses(stdscr, "Press Enter to exit.\n")
        stdscr.getkey()
        exit()

    processed_count = 0

    start_time = time.time()

    while not stop_flag and processed_count < len(urls):
        for i, each in enumerate(urls, 1):
            if stop_flag:
                add_str_to_curses(stdscr, "Stopping process...\n")
                break

            if check_done(each):
                processed_count += 1
                continue

            current_time = datetime.now().strftime("%I:%M %p")
            add_str_to_curses(stdscr, f"\n\n[{i}] Downloading {each} at {current_time} ...\n")
            download_url, last_reset_time, requests_since_reset = get_download_url(each, stdscr, last_reset_time=last_reset_time, requests_since_reset=requests_since_reset)

            stdscr.clear()
            stdscr.addstr(0, 0, banner, curses.color_pair(2))
            display_banner(stdscr, processed_count + 1, len(urls), start_time)

            stdscr.addstr(15, 0, f"Downloading: {each}\n") 

            downloaded_filename = download_from_url(download_url, stdscr, processed_count + 1, len(urls), start_time)
            if downloaded_filename is None:
                continue
            mark_done(each)
            processed_count += 1

            stdscr.nodelay(True)
            if stdscr.getch() == ord('x'):
                stop_flag = True
                add_str_to_curses(stdscr, "Stopping process...\n")
                break

    if processed_count == len(urls):
        add_str_to_curses(stdscr, "All URLs have been processed. Done.\n")
        osu_folder = find_osu_folder(stdscr)
        move_files_confirmation(osu_folder, stdscr)
        time.sleep(5)

    stop_flag = False

def mark_done(mrk):
    """Mark a URL as processed."""
    filename = os.path.join(os.getcwd(), 'done.json')
    if not os.path.exists(filename):
        with open(filename, "w") as fp:
            fp.write(json.dumps([]))

    with open(filename, "r") as fp:
        current = json.loads(fp.read())

    if mrk not in current:
        current.append(mrk)
        with open(filename, "w") as fp:
            fp.write(json.dumps(current))

def get_download_url(url, stdscr, successive_429s=0, last_reset_time=None, requests_since_reset=0):
    """Retrieve the download URL from the provided URL."""
    if last_reset_time and requests_since_reset >= 200:
        time_to_next_reset = 3600 - (time.time() - last_reset_time)
        add_str_to_curses(stdscr, f"Reached rate limit for this hour. Sleeping for {time_to_next_reset} seconds...\n")
        time.sleep(time_to_next_reset)
        last_reset_time = time.time()
        requests_since_reset = 0

    response = httpx.get(url, timeout=None)

    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 30)) * (2 ** successive_429s)
        add_str_to_curses(stdscr, f"Encountered 429 Too Many Requests, sleeping for {retry_after} seconds\n")
        time.sleep(retry_after)
        return get_download_url(url, stdscr, successive_429s + 1, last_reset_time, requests_since_reset)

    if response.status_code == 404:
        add_str_to_curses(stdscr, f"URL {url} returned 404, skipping.\n")
        mark_done(url)
        return None, last_reset_time, requests_since_reset

    if response.status_code == 504:
        add_str_to_curses(stdscr, "Encountered 504 Gateway Timeout, trying again in 1 second...\n")
        time.sleep(1)
        return get_download_url(url, stdscr, successive_429s, last_reset_time, requests_since_reset)

    if response.status_code != 302:
        add_str_to_curses(stdscr, f"Download URL request returned code {response.status_code} instead of 302\n")
        return response.reason_phrase

    download_location = response.headers.get('location')

    if not download_location.startswith("https://"):
        raise ValueError(f"The Gods gave us a bad download location! {download_location}")

    if successive_429s > 0:
        last_reset_time = time.time()
        requests_since_reset = 0

    return download_location, last_reset_time, requests_since_reset + 1

def find_osu_folder(stdscr):
    """Find the osu! folder on the local machine."""
    path = f'C:/users/{os.getlogin()}/appdata/local/osu!'
    if os.path.exists(path):
        return path
    else:
        add_str_to_curses(stdscr, "osu! folder not found. Please move the beatmaps manually.\n")
        return None

def move_files_confirmation(destination_folder, stdscr):
    """Move downloaded files to the osu! Songs folder."""
    if destination_folder is None:
        return

    songs_folder = os.path.join(destination_folder, "Songs")
    os.makedirs(songs_folder, exist_ok=True)

    source_folder = os.path.join(os.getcwd(), 'downloaded')

    if not os.listdir(source_folder):
        stdscr.addstr(18, 0, "The downloads folder is empty. No files to move.\n")
        return

    stdscr.addstr(18, 0, f"Do you want to move all beatmaps to {songs_folder}? (y/n): ")
    stdscr.nodelay(False)
    confirmation = stdscr.getkey()
    if confirmation.lower() != 'y':
        stdscr.addstr(19, 0, "The beatmaps have been left in the download folder.\n")
        stdscr.refresh()
        return

    for filename in os.listdir(source_folder):
        if filename.endswith(".osz"):
            try:
                shutil.move(os.path.join(source_folder, filename), songs_folder)
            except Exception as e:
                add_str_to_curses(stdscr, f"Error moving {filename}: {e}\n")
                continue

    stdscr.addstr(19, 0, f"All files moved to {songs_folder}\n")
    stdscr.refresh()

def clear_console(stdscr):
    """Clear the console."""
    stdscr.clear()
    stdscr.refresh()

def check_for_updates(stdscr):
    """Check for script updates."""
    repo_url = "https://api.github.com/repos/bytewired9/OSZsave/releases/latest"

    try:
        response = httpx.get(repo_url)
        response.raise_for_status()
        latest_version = response.json()["tag_name"]

        if latest_version > CURRENT_VERSION:
            add_str_to_curses(stdscr, f"A new version ({latest_version}) is available!\n")
        elif latest_version < CURRENT_VERSION:
            add_str_to_curses(stdscr, "You're running a developer version!\n")
        else:
            return None
    except Exception as e:
        add_str_to_curses(stdscr, "Could not check for updates. Error: " + str(e) + "\n")

def add_str_to_curses(stdscr, string):
    """Add string to curses interface."""
    try:
        stdscr.addstr(string)
        stdscr.refresh()
    except curses.error:
        pass

if __name__ == "__main__":
    curses.wrapper(main)
