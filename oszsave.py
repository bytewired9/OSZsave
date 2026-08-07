import os
import sys
import re
import time
import json
import httpx
import shutil
import unicodedata
import argparse
import logging
from datetime import datetime
from urllib.parse import unquote, urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from colorama import init
import signal

if getattr(sys, 'frozen', False):
    # Running as a bundled/frozen exe (e.g. PyInstaller) - use the exe's own folder.
    os.chdir(os.path.dirname(sys.executable))
else:
    # Running as a plain .py script - use the script's own folder, not the
    # Python interpreter's install folder (which usually isn't writable).
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
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

CURRENT_VERSION = "1.6.0"

DEBUG_MODE = False
DEBUG_LOG_FILENAME = "oszsave-debug.log"
_debug_logger = None

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="OSZsave - osu! beatmap downloader")
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Print exactly what is sent out and received for every HTTP "
            f"request, both in the UI and to {DEBUG_LOG_FILENAME}."
        ),
    )
    return parser.parse_args()

def init_debug_logging():
    """Set up the debug log file handler. Only called when --debug is passed."""
    global _debug_logger
    logger = logging.getLogger("oszsave.debug")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_path = os.path.join(os.getcwd(), DEBUG_LOG_FILENAME)
    handler = logging.FileHandler(log_path, mode="a", encoding="utf_8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)

    _debug_logger = logger
    logger.debug("=" * 80)
    logger.debug(f"OSZsave {CURRENT_VERSION} debug session started")
    return log_path

def debug_log(stdscr, message):
    """
    Log a debug message to both the curses UI and the debug log file.
    No-op unless --debug was passed. Multi-line messages are indented
    for readability in both destinations.
    """
    if not DEBUG_MODE:
        return

    if _debug_logger is not None:
        _debug_logger.debug(message)

    add_str_to_curses(stdscr, message.rstrip("\n") + "\n")

def format_request_debug(method, url, headers=None):
    """Format an outgoing request for debug logging."""
    lines = [f"--> {method} {url}"]
    if headers:
        for k, v in headers.items():
            lines.append(f"    {k}: {v}")
    return "\n".join(lines)

def format_response_debug(response, body_preview_bytes=None):
    """Format a received response for debug logging."""
    lines = [f"<-- {response.status_code} {response.url}"]
    for k, v in response.headers.items():
        lines.append(f"    {k}: {v}")
    if body_preview_bytes is not None:
        preview = body_preview_bytes[:200]
        try:
            preview_str = preview.decode("utf_8", errors="replace")
        except Exception:
            preview_str = repr(preview)
        suffix = "..." if len(body_preview_bytes) > 200 else ""
        lines.append(f"    body preview: {preview_str}{suffix}")
    return "\n".join(lines)

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
    add_str_to_curses(stdscr, "Searching for 'show more' buttons...\n")
    sections_to_scroll = ["recent_activity", "top_ranks", "medals", "historical", "beatmaps"]
    sections_expanded = 0
    start_time = time.time()

    for section in sections_to_scroll:
        scroll_to_section(driver, section)
        # Give the section time to potentially load initial content
        time.sleep(1) 
        
        while True:
            try:
                # Find the button. This will get a fresh reference in each loop iteration.
                wait = WebDriverWait(driver, 2)
                btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".show-more-link--profile-page")))
                
                # Scroll to the button and click it
                driver.execute_script("arguments[0].scrollIntoView({ behavior: 'auto', block: 'center' });", btn)
                btn.click()
                
                # Wait for the new content to load after the click
                time.sleep(1)
                
                sections_expanded += 1
                elapsed_time = time.time() - start_time
                add_str_to_curses(stdscr, f'\rExpanding link sections. [Sections expanded: {sections_expanded}; Time elapsed: {elapsed_time:.2f} seconds]')

            except TimeoutException:
                # This is the expected exit condition: no more "show more" buttons are found.
                add_str_to_curses(stdscr, f"\nNo more 'show more' buttons in section '{section}'. Moving on.\n")
                break # Exit the while loop for the current section

            except StaleElementReferenceException:
                # The button was clicked, but the page changed, making the reference stale.
                # Simply continue the loop to find the button again in the new DOM.
                add_str_to_curses(stdscr, "\nStale element detected, re-locating...")
                continue

    add_str_to_curses(stdscr, "\nFinished expanding all sections. Proceeding to collect links!\n")
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

    # Sorted rather than set-order so the run order is stable between runs,
    # which makes resuming an interrupted batch predictable.
    unique_paydirt = sorted(set(paydirt_modified))

    filename = os.path.join(os.getcwd(), 'beatmap_list.json')
    write_json_atomic(filename, unique_paydirt)

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
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
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

def write_json_atomic(path, data):
    """
    Write JSON by writing to a temp file and renaming over the target.
    A crash or Ctrl-C mid-write then leaves the previous good file intact
    instead of a truncated one that fails to parse on the next run.
    """
    temp_path = path + '.tmp'
    with open(temp_path, 'w', encoding="utf_8") as fp:
        json.dump(data, fp, indent=4)
        fp.flush()
        os.fsync(fp.fileno())
    os.replace(temp_path, path)

def read_json_list(path, stdscr=None, default=None):
    """
    Read a JSON list, recovering gracefully if the file is corrupt.
    A damaged done.json shouldn't make the program unusable - worst case we
    re-download some maps, which is far better than refusing to start.
    """
    if default is None:
        default = []
    if not os.path.exists(path):
        return list(default)
    try:
        with open(path, "r", encoding="utf_8") as fp:
            data = json.load(fp)
        if not isinstance(data, list):
            raise ValueError("expected a JSON list")
        return data
    except (OSError, ValueError) as e:
        if stdscr is not None:
            add_str_to_curses(stdscr, f"Could not read {os.path.basename(path)} ({e}).\n")
        # Preserve the damaged file for inspection rather than silently losing it.
        try:
            backup = path + '.corrupt'
            os.replace(path, backup)
            if stdscr is not None:
                add_str_to_curses(stdscr, f"Moved the damaged file to {os.path.basename(backup)}.\n")
        except OSError:
            pass
        return list(default)

def get_urls(stdscr, filename=None):
    """Retrieve URLs from the JSON file."""
    if filename is None:
        filename = os.path.join(os.getcwd(), 'beatmap_list.json')

    if not os.path.exists(filename):
        write_json_atomic(filename, [])
        add_str_to_curses(stdscr, f"Please enter the URLs in {filename}\n")
        add_str_to_curses(stdscr, 'Press Enter to Exit\n')
        stdscr.getkey()
        exit()

    urls = read_json_list(filename, stdscr)
    if not urls:
        add_str_to_curses(stdscr, f"The {filename} file is empty.\n")
        add_str_to_curses(stdscr, 'Press Enter to Exit\n')
        stdscr.getkey()
        exit()

    return urls

# done.json is read once and kept in memory. The original code re-read and
# re-parsed the whole file for every beatmap, which got quadratically slower
# as the done list grew.
_done_cache = None

def _done_path():
    return os.path.join(os.getcwd(), 'done.json')

def load_done(stdscr=None):
    """Load the set of already-processed URLs into memory."""
    global _done_cache
    if _done_cache is None:
        _done_cache = set(read_json_list(_done_path(), stdscr))
    return _done_cache

def check_done(chk):
    """Check if the URL has already been processed."""
    return chk in load_done()

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

# ---------------------------------------------------------------------------
# Mirror configuration and health tracking
# ---------------------------------------------------------------------------
# Mirrors are defined in an external JSON file so that when a mirror changes
# its URL scheme, starts requiring a header, or dies outright, users can fix
# it themselves without waiting for a new release. The defaults below are
# written out on first run if the file doesn't exist.

MIRRORS_CONFIG_FILENAME = "mirrors.json"

DEFAULT_MIRRORS = [
    {
        "name": "catboy",
        "url": "https://catboy.best/d/{id}",
        "headers": {"User-Agent": "OSZsave"},
        "timeout": 10,
        "enabled": True,
    },
    {
        "name": "nekoha",
        "url": "https://mirror.nekoha.moe/api/download/{id}",
        "headers": {"User-Agent": "OSZsave"},
        "timeout": 10,
        "enabled": True,
    },
    {
        "name": "beatconnect",
        "url": "https://beatconnect.io/b/{id}/",
        "headers": {"User-Agent": "OSZsave"},
        "timeout": 5,
        "enabled": True,
    },
]

# Minimum seconds to wait between requests to a given mirror host, and how
# long to back off after that mirror returns a 429, keyed by hostname.
# This is intentionally conservative (rather than pulling numbers from each
# mirror's ever-changing ratelimit docs) since being wrong in the
# "wait longer" direction just costs time, while being wrong in the
# "wait less" direction risks a ban.
MIRROR_MIN_INTERVAL = 1.0
MIRROR_429_BACKOFF_BASE = 30

# Cap retry recursion when resolving a download URL so a persistently rate
# limited or timing-out endpoint can't recurse or sleep unbounded.
MAX_SUCCESSIVE_429S = 5

# A mirror that fails this many times in a row is skipped for the rest of the
# run. Prevents a dead mirror from taxing every single beatmap with a timeout.
MIRROR_MAX_CONSECUTIVE_FAILURES = 8

_mirror_last_request = {}
_mirror_backoff_until = {}
_mirror_stats = {}
_mirrors = []

def _stats_for(name):
    """Get (creating if needed) the running stats record for a mirror."""
    if name not in _mirror_stats:
        _mirror_stats[name] = {
            "success": 0,
            "failure": 0,
            "consecutive_failures": 0,
            "bytes": 0,
            "last_error": None,
            "disabled": False,
        }
    return _mirror_stats[name]

def record_mirror_success(name, byte_count):
    """Record a successful download from a mirror."""
    s = _stats_for(name)
    s["success"] += 1
    s["consecutive_failures"] = 0
    s["bytes"] += byte_count

def record_mirror_failure(name, reason, stdscr=None):
    """Record a failed attempt against a mirror, disabling it if it keeps failing."""
    s = _stats_for(name)
    s["failure"] += 1
    s["consecutive_failures"] += 1
    s["last_error"] = reason

    if (not s["disabled"]
            and s["consecutive_failures"] >= MIRROR_MAX_CONSECUTIVE_FAILURES):
        s["disabled"] = True
        if stdscr is not None:
            add_str_to_curses(
                stdscr,
                f"Mirror '{name}' failed {s['consecutive_failures']} times in a row "
                f"({reason}). Skipping it for the rest of this run.\n"
            )

def validate_mirror(entry):
    """
    Return an error string if this mirror config entry is unusable, else None.
    Keeps a malformed hand-edited mirrors.json from crashing the whole run.
    """
    if not isinstance(entry, dict):
        return "entry is not a JSON object"
    name = entry.get("name")
    if not name or not isinstance(name, str):
        return "missing or invalid 'name'"
    url = entry.get("url")
    if not url or not isinstance(url, str):
        return f"mirror '{name}' is missing or has an invalid 'url'"
    if "{id}" not in url:
        return f"mirror '{name}' url must contain the '{{id}}' placeholder"
    if not url.startswith(("http://", "https://")):
        return f"mirror '{name}' url must start with http:// or https://"
    headers = entry.get("headers")
    if headers is not None and not isinstance(headers, dict):
        return f"mirror '{name}' has a non-object 'headers'"
    timeout = entry.get("timeout", 10)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        return f"mirror '{name}' has an invalid 'timeout'"
    return None

def load_mirrors(stdscr):
    """
    Load the mirror list from mirrors.json, writing the defaults out on first
    run. Falls back to the built-in defaults if the file is missing/corrupt so
    that a bad config never leaves the user with no way to download.
    """
    global _mirrors
    path = os.path.join(os.getcwd(), MIRRORS_CONFIG_FILENAME)

    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf_8") as fp:
                json.dump(DEFAULT_MIRRORS, fp, indent=4)
            add_str_to_curses(stdscr, f"Created default mirror config at {path}\n")
        except OSError as e:
            add_str_to_curses(stdscr, f"Could not write {MIRRORS_CONFIG_FILENAME}: {e}. Using built-in defaults.\n")
        _mirrors = [dict(m) for m in DEFAULT_MIRRORS]
        return _mirrors

    try:
        with open(path, "r", encoding="utf_8") as fp:
            loaded = json.load(fp)
    except (OSError, json.JSONDecodeError) as e:
        add_str_to_curses(stdscr, f"Could not read {MIRRORS_CONFIG_FILENAME} ({e}). Using built-in defaults.\n")
        _mirrors = [dict(m) for m in DEFAULT_MIRRORS]
        return _mirrors

    if not isinstance(loaded, list):
        add_str_to_curses(stdscr, f"{MIRRORS_CONFIG_FILENAME} must contain a JSON list. Using built-in defaults.\n")
        _mirrors = [dict(m) for m in DEFAULT_MIRRORS]
        return _mirrors

    valid = []
    for entry in loaded:
        problem = validate_mirror(entry)
        if problem:
            add_str_to_curses(stdscr, f"Ignoring bad mirror config: {problem}\n")
            continue
        if entry.get("enabled", True) is False:
            debug_log(stdscr, f"Mirror '{entry['name']}' is disabled in config, skipping.")
            continue
        valid.append(entry)

    if not valid:
        add_str_to_curses(stdscr, f"No usable mirrors in {MIRRORS_CONFIG_FILENAME}. Using built-in defaults.\n")
        _mirrors = [dict(m) for m in DEFAULT_MIRRORS]
        return _mirrors

    _mirrors = valid
    debug_log(stdscr, f"Loaded {len(valid)} mirror(s) from {path}: {', '.join(m['name'] for m in valid)}")
    return _mirrors

def ordered_mirrors():
    """
    Return the mirror list ordered best-first for this moment:
      - mirrors disabled after repeated failure go last (and are skipped anyway)
      - then by success rate, descending
      - config order breaks ties, so a fresh run honors the user's preference
    This means a mirror that starts failing naturally sinks down the list
    instead of costing every subsequent beatmap a wasted timeout.
    """
    def sort_key(item):
        index, mirror = item
        s = _stats_for(mirror["name"])
        attempts = s["success"] + s["failure"]
        # Unattempted mirrors sort as neutral so config order leads initially.
        rate = (s["success"] / attempts) if attempts else 0.5
        return (s["disabled"], -rate, index)

    return [m for _, m in sorted(enumerate(_mirrors), key=sort_key)]

def mirror_summary_lines():
    """Build a human-readable per-mirror summary of this run."""
    lines = []
    for mirror in _mirrors:
        name = mirror["name"]
        s = _stats_for(name)
        attempts = s["success"] + s["failure"]
        if not attempts:
            lines.append(f"  {name}: not used")
            continue
        mb = s["bytes"] / (1024 * 1024)
        line = f"  {name}: {s['success']}/{attempts} ok, {mb:.1f} MB"
        if s["disabled"]:
            line += " [disabled after repeated failures]"
        if s["last_error"]:
            line += f" (last error: {s['last_error']})"
        lines.append(line)
    return lines

def _mirror_host(source_url):
    """Extract a host key (scheme+netloc) from a mirror URL for rate tracking."""
    match = re.match(r'(https?://[^/]+)', source_url)
    return match.group(1) if match else source_url

def _wait_for_mirror(source_url, stdscr):
    """Respect per-mirror pacing and any active 429 backoff before requesting."""
    host = _mirror_host(source_url)
    now = time.time()

    backoff_until = _mirror_backoff_until.get(host)
    if backoff_until and now < backoff_until:
        wait_for = backoff_until - now
        add_str_to_curses(stdscr, f"{host} is in backoff, waiting {wait_for:.1f}s...\n")
        time.sleep(wait_for)
        now = time.time()

    last = _mirror_last_request.get(host)
    if last is not None:
        elapsed = now - last
        if elapsed < MIRROR_MIN_INTERVAL:
            time.sleep(MIRROR_MIN_INTERVAL - elapsed)

    _mirror_last_request[host] = time.time()

def _register_429(source_url, retry_after_header, stdscr):
    """Record a 429 for this mirror and set a backoff window before it's tried again."""
    host = _mirror_host(source_url)

    backoff_seconds = MIRROR_429_BACKOFF_BASE
    if retry_after_header:
        # Retry-After may be an integer (seconds) or, per some mirrors' newer
        # APIs, a UTC datetime string. Handle both.
        try:
            backoff_seconds = int(retry_after_header)
        except ValueError:
            try:
                retry_dt = datetime.strptime(retry_after_header, "%a, %d %b %Y %H:%M:%S GMT")
                backoff_seconds = max(0, (retry_dt - datetime.utcnow()).total_seconds())
            except ValueError:
                try:
                    retry_dt = datetime.fromisoformat(retry_after_header.replace("Z", "+00:00"))
                    backoff_seconds = max(0, (retry_dt - datetime.now(retry_dt.tzinfo)).total_seconds())
                except ValueError:
                    add_str_to_curses(stdscr, f"Could not parse Retry-After value '{retry_after_header}', using default backoff.\n")

    # Don't let a hostile or buggy header park us for hours.
    backoff_seconds = max(0, min(backoff_seconds, 3600))

    _mirror_backoff_until[host] = time.time() + backoff_seconds
    add_str_to_curses(stdscr, f"{host} rate limited us (429). Backing off for {backoff_seconds:.0f}s before retrying this mirror.\n")

def looks_like_osz(first_bytes):
    """
    An .osz is a zip archive, so it must start with a zip magic number.
    Mirrors sometimes return an HTML error page or a JSON error body with a
    200 status; without this check that garbage gets saved as a .osz and then
    permanently marked done.
    """
    return first_bytes.startswith(b"PK\x03\x04") or first_bytes.startswith(b"PK\x05\x06")

def download_from_url(url, stdscr, current, total, start_time):
    """Download file from the provided URL, trying each configured mirror in turn."""
    if url is None:
        add_str_to_curses(stdscr, "URL is None, skipping download.\n")
        return None

    pattern = r'https://osu\.ppy\.sh/beatmapsets/(\d+)'
    match = re.search(pattern, url)
    if not match:
        add_str_to_curses(stdscr, f"Could not parse a beatmapset ID out of {url}, skipping.\n")
        debug_log(stdscr, f"Unparseable download URL: {url}")
        return None
    level_id = match.group(1)

    for mirror in ordered_mirrors():
        if stop_flag:
            return None

        name = mirror["name"]
        stats = _stats_for(name)
        if stats["disabled"]:
            debug_log(stdscr, f"Skipping disabled mirror '{name}'.")
            continue

        source_url = mirror["url"].replace("{id}", level_id)
        headers = mirror.get("headers") or None
        timeout = mirror.get("timeout", 10)

        add_str_to_curses(stdscr, f"Trying {name}: {source_url}\n")
        _wait_for_mirror(source_url, stdscr)

        temp_path = None
        try:
            debug_log(stdscr, format_request_debug("GET", source_url, headers=headers))
            with httpx.stream("GET", source_url, timeout=timeout, headers=headers,
                              follow_redirects=True) as r:
                debug_log(stdscr, format_response_debug(r))

                if r.status_code == 429:
                    _register_429(source_url, r.headers.get('Retry-After'), stdscr)
                    record_mirror_failure(name, "429 rate limited", stdscr)
                    add_str_to_curses(stdscr, "Trying next source...\n")
                    continue

                if r.status_code != 200:
                    # Error bodies are small and often explain the refusal
                    # (WAF block page, "API key required", etc). Worth logging.
                    body_preview = b""
                    try:
                        body_preview = r.read()[:200]
                    except Exception:
                        pass
                    debug_log(stdscr, format_response_debug(r, body_preview_bytes=body_preview))
                    record_mirror_failure(name, f"HTTP {r.status_code}", stdscr)
                    add_str_to_curses(stdscr, f"Failed with status code {r.status_code}. Trying next source...\n")
                    continue

                cd = r.headers.get('content-disposition')
                try:
                    encoded_filename = re.findall("filename=(.+)", cd)[0].strip('"; ')
                    filename = unquote(encoded_filename)
                except Exception:
                    filename = f'{level_id}.osz'

                if not filename.lower().endswith('.osz'):
                    filename += '.osz'

                sanitized_filename = sanitize(filename)

                download_path = os.path.join(os.getcwd(), 'downloaded')
                os.makedirs(download_path, exist_ok=True)
                full_path = os.path.join(download_path, sanitized_filename)
                # Write to a .part file first so an interrupted or corrupt
                # download never leaves something that looks like a finished map.
                temp_path = full_path + '.part'

                total_bytes = int(r.headers.get("content-length", 0))
                progress = 0
                first_chunk_checked = False
                bad_content = False

                with open(temp_path, "wb") as fp:
                    for data in r.iter_bytes():
                        # Check for stop flag before processing each chunk
                        if stop_flag:
                            add_str_to_curses(stdscr, "Stopping download...\n")
                            raise KeyboardInterrupt

                        if not first_chunk_checked and data:
                            first_chunk_checked = True
                            if not looks_like_osz(data):
                                bad_content = True
                                debug_log(
                                    stdscr,
                                    f"{name} returned 200 but body is not a zip/.osz "
                                    f"(first bytes: {data[:32]!r})"
                                )
                                break

                        progress += len(data)
                        fp.write(data)
                        display_progress_bar(stdscr, progress, total_bytes, sanitized_filename)

                if bad_content:
                    _cleanup_temp(temp_path)
                    record_mirror_failure(name, "200 but not a valid .osz", stdscr)
                    add_str_to_curses(stdscr, "Response was not a valid beatmap file. Trying next source...\n")
                    continue

                # A truncated transfer still reaches this point, so verify the
                # byte count against Content-Length when the server gave one.
                if total_bytes and progress != total_bytes:
                    _cleanup_temp(temp_path)
                    record_mirror_failure(name, f"truncated ({progress}/{total_bytes} bytes)", stdscr)
                    debug_log(stdscr, f"{name} truncated: got {progress} of {total_bytes} bytes")
                    add_str_to_curses(stdscr, "Download was incomplete. Trying next source...\n")
                    continue

                if progress == 0:
                    _cleanup_temp(temp_path)
                    record_mirror_failure(name, "empty response", stdscr)
                    add_str_to_curses(stdscr, "Got an empty file. Trying next source...\n")
                    continue

                os.replace(temp_path, full_path)
                temp_path = None
                record_mirror_success(name, progress)
                debug_log(stdscr, f"Download complete via {name}: {full_path} ({progress} bytes)")
                return full_path

        except KeyboardInterrupt:
            _cleanup_temp(temp_path)
            return None
        except httpx.TimeoutException:
            _cleanup_temp(temp_path)
            record_mirror_failure(name, "timed out", stdscr)
            debug_log(stdscr, f"Timeout on {source_url}")
            add_str_to_curses(stdscr, "Hm. This is taking a while, let's try a different one.\n")
        except httpx.RequestError as e:
            _cleanup_temp(temp_path)
            record_mirror_failure(name, f"request error: {e}", stdscr)
            debug_log(stdscr, f"Request error on {source_url}: {e}")
            add_str_to_curses(stdscr, f"Request error: {e}. Trying next source...\n")
        except OSError as e:
            # Disk full, permission denied, path too long, etc. Worth being
            # loud about since it's a local problem no other mirror will fix.
            _cleanup_temp(temp_path)
            record_mirror_failure(name, f"file error: {e}", stdscr)
            debug_log(stdscr, f"File error while saving from {source_url}: {e}")
            add_str_to_curses(stdscr, f"Could not write the file: {e}\n")
        except Exception as e:
            # Anything unexpected should cost us one mirror, not the whole run.
            _cleanup_temp(temp_path)
            record_mirror_failure(name, f"{type(e).__name__}: {e}", stdscr)
            debug_log(stdscr, f"Unexpected {type(e).__name__} on {source_url}: {e}")
            add_str_to_curses(stdscr, f"Unexpected error ({type(e).__name__}). Trying next source...\n")

    add_str_to_curses(stdscr, "All sources failed. Moving to the next URL.\n")
    return None

def _cleanup_temp(temp_path):
    """Remove a partial download file, ignoring any error doing so."""
    if not temp_path:
        return
    try:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    except OSError:
        pass

def main(stdscr):
    """Main function to start the application."""
    global stop_flag
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)

    clear_console(stdscr)
    stdscr.addstr(0, 0, banner, curses.color_pair(2))
    stdscr.refresh()

    if DEBUG_MODE:
        debug_log(stdscr, f"Debug mode enabled. Logging to {os.path.join(os.getcwd(), DEBUG_LOG_FILENAME)}")

    load_mirrors(stdscr)
    cleanup_stale_parts(stdscr)
    load_done(stdscr)

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
    # URLs that failed this run. Tracked so a permanently-failing map can't
    # trap the outer loop retrying it forever.
    failed = set()

    start_time = time.time()

    while not stop_flag and (processed_count + len(failed)) < len(urls):
        for i, each in enumerate(urls, 1):
            if stop_flag:
                add_str_to_curses(stdscr, "Stopping process...\n")
                break

            if check_done(each) or each in failed:
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
                failed.add(each)
                continue
            mark_done(each)
            processed_count += 1

            stdscr.nodelay(True)
            if stdscr.getch() == ord('x'):
                stop_flag = True
                add_str_to_curses(stdscr, "Stopping process...\n")
                break

    show_run_summary(stdscr, processed_count, len(urls), failed, start_time)

    if processed_count == len(urls):
        add_str_to_curses(stdscr, "All URLs have been processed. Done.\n")
        osu_folder = find_osu_folder(stdscr)
        move_files_confirmation(osu_folder, stdscr)
        time.sleep(5)
    elif failed:
        add_str_to_curses(stdscr, f"\n{len(failed)} map(s) could not be downloaded from any mirror.\n")
        add_str_to_curses(stdscr, "They were NOT marked done, so re-running will retry them.\n")
        add_str_to_curses(stdscr, "Press Enter to continue.\n")
        try:
            stdscr.nodelay(False)
            stdscr.getkey()
        except curses.error:
            pass

    stop_flag = False

def cleanup_stale_parts(stdscr):
    """
    Remove leftover .part files from a previous interrupted run so they don't
    accumulate, and so a half-file is never mistaken for a real beatmap.
    """
    download_path = os.path.join(os.getcwd(), 'downloaded')
    if not os.path.isdir(download_path):
        return

    removed = 0
    try:
        for name in os.listdir(download_path):
            if name.endswith('.part'):
                try:
                    os.remove(os.path.join(download_path, name))
                    removed += 1
                except OSError:
                    pass
    except OSError:
        return

    if removed:
        add_str_to_curses(stdscr, f"Cleaned up {removed} incomplete download(s) from a previous run.\n")

def show_run_summary(stdscr, processed_count, total, failed, start_time):
    """Print a per-mirror summary so a degrading mirror is visible immediately."""
    elapsed = time.time() - start_time
    minutes, seconds = divmod(int(elapsed), 60)

    lines = [
        "",
        "---- Run summary ----",
        f"  Downloaded: {processed_count}/{total}",
        f"  Failed:     {len(failed)}",
        f"  Elapsed:    {minutes:02}:{seconds:02}",
        "  Mirrors:",
    ]
    lines.extend(mirror_summary_lines())

    for line in lines:
        add_str_to_curses(stdscr, line + "\n")
        if _debug_logger is not None:
            _debug_logger.debug(line)

def mark_done(mrk):
    """Mark a URL as processed."""
    done = load_done()
    if mrk in done:
        return

    done.add(mrk)
    try:
        write_json_atomic(_done_path(), sorted(done))
    except OSError:
        # Losing one done-entry just means re-downloading that map next run,
        # which is not worth crashing over mid-batch.
        pass

def get_download_url(url, stdscr, successive_429s=0, last_reset_time=None, requests_since_reset=0):
    """Retrieve the download URL from the provided URL."""
    if last_reset_time and requests_since_reset >= 200:
        time_to_next_reset = 3600 - (time.time() - last_reset_time)
        add_str_to_curses(stdscr, f"Reached rate limit for this hour. Sleeping for {time_to_next_reset} seconds...\n")
        time.sleep(time_to_next_reset)
        last_reset_time = time.time()
        requests_since_reset = 0

    try:
        debug_log(stdscr, format_request_debug("GET", url))
        response = httpx.get(url, timeout=30)
        debug_log(stdscr, format_response_debug(response, body_preview_bytes=response.content[:200]))
    except Exception as e:
        # A network blip resolving one map shouldn't end the batch.
        debug_log(stdscr, f"Error resolving {url}: {type(e).__name__}: {e}")
        add_str_to_curses(stdscr, f"Could not resolve {url} ({type(e).__name__}). Skipping.\n")
        return None, last_reset_time, requests_since_reset

    if response.status_code == 429:
        # Cap the recursion so a permanently rate-limited endpoint can't blow
        # the stack or sleep for an unbounded amount of time.
        if successive_429s >= MAX_SUCCESSIVE_429S:
            add_str_to_curses(stdscr, f"Still rate limited after {successive_429s} retries. Skipping this URL.\n")
            return None, last_reset_time, requests_since_reset

        try:
            base_retry = int(response.headers.get('Retry-After', 30))
        except (TypeError, ValueError):
            base_retry = 30
        retry_after = min(base_retry * (2 ** successive_429s), 900)
        add_str_to_curses(stdscr, f"Encountered 429 Too Many Requests, sleeping for {retry_after} seconds\n")
        time.sleep(retry_after)
        return get_download_url(url, stdscr, successive_429s + 1, last_reset_time, requests_since_reset)

    if response.status_code == 404:
        add_str_to_curses(stdscr, f"URL {url} returned 404, skipping.\n")
        mark_done(url)
        return None, last_reset_time, requests_since_reset

    if response.status_code == 504:
        if successive_429s >= MAX_SUCCESSIVE_429S:
            add_str_to_curses(stdscr, "Gateway kept timing out. Skipping this URL.\n")
            return None, last_reset_time, requests_since_reset
        add_str_to_curses(stdscr, "Encountered 504 Gateway Timeout, trying again in 1 second...\n")
        time.sleep(1)
        return get_download_url(url, stdscr, successive_429s + 1, last_reset_time, requests_since_reset)

    if response.status_code != 302:
        # Must return the same 3-tuple shape every caller unpacks; the original
        # returned a bare string here, which crashed the run.
        add_str_to_curses(stdscr, f"Download URL request returned code {response.status_code} instead of 302\n")
        return None, last_reset_time, requests_since_reset

    download_location = response.headers.get('location')

    if not download_location or not download_location.startswith("https://"):
        # Skip rather than raise - one odd redirect shouldn't end the batch.
        add_str_to_curses(stdscr, f"Got an unusable download location, skipping: {download_location}\n")
        debug_log(stdscr, f"Bad download location for {url}: {download_location!r}")
        return None, last_reset_time, requests_since_reset

    if successive_429s > 0:
        last_reset_time = time.time()
        requests_since_reset = 0

    return download_location, last_reset_time, requests_since_reset + 1

def find_osu_folder(stdscr):
    """Find the osu! folder on the local machine."""
    candidates = []

    # os.getlogin() raises in some environments (no controlling terminal,
    # services, some IDEs), so prefer the environment/expanduser route.
    localappdata = os.environ.get('LOCALAPPDATA')
    if localappdata:
        candidates.append(os.path.join(localappdata, 'osu!'))

    home = os.path.expanduser('~')
    candidates.extend([
        os.path.join(home, 'AppData', 'Local', 'osu!'),
        os.path.join(home, '.local', 'share', 'osu-stable'),
        os.path.join(home, 'Library', 'Application Support', 'osu!'),
    ])

    for path in candidates:
        if os.path.isdir(path):
            debug_log(stdscr, f"Found osu! folder at {path}")
            return path

    add_str_to_curses(stdscr, "osu! folder not found. Please move the beatmaps manually.\n")
    debug_log(stdscr, f"No osu! folder found. Checked: {candidates}")
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
        debug_log(stdscr, format_request_debug("GET", repo_url))
        response = httpx.get(repo_url)
        debug_log(stdscr, format_response_debug(response, body_preview_bytes=response.content[:200]))
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
    args = parse_args()
    DEBUG_MODE = args.debug
    if DEBUG_MODE:
        log_path = init_debug_logging()
        print(f"Debug mode enabled. Logging to {log_path}")
    curses.wrapper(main)