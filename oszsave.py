import httpx
from urllib import parse
import os
import time  # Add this import to the top of your script
import unicodedata
import re
import json
import random
from datetime import datetime

import os

script_file_path = 'script.js'

# Check if the script file exists
if not os.path.exists(script_file_path):
    js_script_content = """
let paydirt = [];
let targets = ["play-detail__title", "beatmapset-panel__main-link", "profile-extra-entries__text", "beatmap-playcount__title"];

function findNextButtons() {
    console.log("Searching for 'next' buttons...");
    let btn = document.getElementsByClassName("show-more-link--profile-page")[0];
    if (btn) {
        console.log("Found a 'next' button, clicking...");
        btn.scrollIntoView({ behavior: "auto", block: "center" }); // Auto scroll to 'next' button
        btn.click();
        setTimeout(findNextButtons, 1000); // Wait for 1 second before searching for the next button again
    } else {
        console.log("No more 'next' buttons found, start digging gold!");
        digForGold();
    }
}

async function digForGold() {
    console.log("Start collecting URLs...");

    let targetElements = Array.from(document.querySelectorAll(targets.map(target => `.${target}`).join(', ')));
    let targetLinks = Array.from(document.querySelectorAll(targets.map(target => `a.${target}`).join(', ')));

    let allLinks = [...targetElements.flatMap(element => Array.from(element.querySelectorAll('a'))), ...targetLinks];

    for (let link of allLinks) {
        let newUrl = link.href;

        if (!paydirt.includes(newUrl) && 
            !newUrl.startsWith("https://osu.ppy.sh/u") && 
            !newUrl.endsWith("/discussion") &&
            !newUrl.includes("https://osu.ppy.sh/beatmapsets/discussions/")) {
            link.scrollIntoView({ behavior: "auto", block: "center" }); // Auto scroll to each link
            paydirt.push(newUrl);
            await new Promise(resolve => setTimeout(resolve, 10)); // Wait for 50ms before scrolling to the next link
        }
    }

    console.log("End collecting URLs...");
    processPaydirt();
}

function processPaydirt() {
    console.log("Gold digging completed, processing URLs...");
    let paydirtModified = paydirt.map(url => {
        let match = url.match(/\\/b\\/([0-9]+)\\?[A-Za-z]=[0-9]+/);
        if (match) {
            return `https://osu.ppy.sh/beatmapsets/${match[1]}/download`;
        } else if (url.match(/https:\\/\\/osu\\.ppy\\.sh\\/beatmapsets\\/[0-9]+$/)) {
            return url + "/download"; // Appending download to URLs with the specific pattern
        } else {
            return url.replace(/#[A-Za-z]+\\/[0-9]+/g, '/download');
        }
    });

    let uniquePaydirt = [...new Set(paydirtModified)]; // Ensuring uniqueness
    console.log("Final processed list of URLs:");
    console.log(JSON.stringify(uniquePaydirt, null, 4));
}

console.log("Script started...");
findNextButtons();
    """

    with open(script_file_path, 'w') as file:
        file.write(js_script_content.lstrip())
        print(f"{script_file_path} created.")

def create_instructions_file():
    instructions = """
    Getting Headers:
    - Go to osu.ppy.sh
    - Go to the beatmaps page
    - Go to a random beatmap
    - Open the network page (use F12 or right-click the page and select 'Inspect', then go to the 'Network' tab)
    - Click the download button on the beatmap (note: you don't have to save it, just click)
    - Find the packet that is titled "download"
    - Right-click it and choose 'Copy as cURL (bash)'
    - Paste that into curl_command.txt

    Getting Beatmap Links:
    - Go to osu.ppy.sh
    - Go to your desired user profile
    - Open your browser's JS console window by pressing F12 or right-clicking the page and selecting 'Inspect', then go to the 'Console' tab
    - Paste the script from script.js into there
    - Let it run
    - Once it is finished you will have a list of beatmap links, paste them into beatmap_links.json

    Running:
    - Once all of these are done, run the program

    Importing Beatmaps:
    - Once all of the beatmaps have finished downloading, open osu!
    - Make sure osu is not in fullscreen mode
    - Select all the files from the 'downloaded' folder and drag them into the osu! window
    - Enjoy the maps

    Note on Runtime:
    - Please be aware that the program could take up to several hours to complete if you are processing a large list of beatmaps. Make sure to plan accordingly and be patient.

    Need Help?
    - If you encounter any problems or have any questions about the process, feel free to reach out to me on Discord: @forgedcore8. I'll be happy to assist you!
    """

    with open('instructions.txt', 'w') as file:
        file.write(instructions)
        print("Instructions file created.")

create_instructions_file()


def extract_headers(curl_command):
    headers = {}
    matches = re.findall(r"-H '(.*?)'", curl_command)
    for match in matches:
        key, value = match.split(": ", 1)
        headers[key] = value
    return headers

def get_headers():
    config_path = os.path.join(os.path.dirname(__file__), 'config')
    input_filename = os.path.join(config_path, 'curl_command.txt')
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

    with open(input_filename, "r") as file:
        curl_command = file.read()

    headers = extract_headers(curl_command)

    try:
        with open(output_filename, "r") as file:
            existing_headers = json.load(file)
            # Check if the existing headers are non-empty and match the current headers
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

    return headers



headers = get_headers()


def get_urls(filename=None):
    config_path = os.path.join(os.path.dirname(__file__), 'config')
    if filename is None:
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

    with open(filename, "r") as fp:
        urls = json.load(fp)
        if not urls:
            print(f"The {filename} file is empty.")
            print('Press Enter to Exit')
            input()
            exit()
        return urls


def check_done(chk):
    filename = os.path.join(os.path.dirname(__file__), '..', 'config', 'done.json')

    # Create file if not exists
    if not os.path.exists(filename):
        with open(filename, 'w') as file:
            file.write("[]")

    with open(filename, "r") as fp:
        done = json.loads(fp.read())
        return bool(chk in done)

urls = get_urls()


def sanitize(filename):
  blacklist = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0"]
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
  filename = "".join(c for c in filename if c not in blacklist)
  filename = "".join(c for c in filename if 31 < ord(c))
  filename = unicodedata.normalize("NFKD", filename)
  filename = filename.rstrip(". ")
  filename = filename.strip()
  if all([x == "." for x in filename]):
    filename = "__" + filename
  if filename in reserved:
    filename = "__" + filename
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
    if len(ext) > 254:
      ext = ext[254:]
    maxl = 255 - len(ext)
    filename = filename[:maxl]
    filename = filename + ext
    filename = filename.rstrip(". ")
    if len(filename) == 0:
      filename = "__"
  return filename

def download_from_url(url):
    if url is None:
        print("URL is None, skipping download.")
        return None
    qs = parse.parse_qs(url)
    download_path = os.path.join(os.path.dirname(__file__), 'downloaded')
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    filename = os.path.join(download_path, sanitize(qs[list(qs.keys())[0]][0]))
    with open(filename, "wb") as fp, httpx.stream("GET", url, headers=headers, timeout=None) as r:
        for data in r.iter_bytes():
            fp.write(data)
    return filename


def check_done(chk):
    filename = os.path.join(os.path.dirname(__file__), 'config', 'done.json')
    if not os.path.exists(filename):
        with open(filename, "w") as fp:
            fp.write(json.dumps([]))
    with open(filename, "r") as fp:
        done = json.loads(fp.read())
        return bool(chk in done)


def mark_done(mrk):
    filename = os.path.join(os.path.dirname(__file__), 'config', 'done.json')
    current = None
    if not os.path.exists(filename):
        with open(filename, "w") as fp:
            fp.write(json.dumps([]))
    with open(filename, "r") as fp:
        current = json.loads(fp.read())
    if mrk not in current:
        current.append(mrk)
        with open(filename, "w") as fp:
            fp.write(json.dumps(current))


def get_download_url(url, successive_429s=0, last_reset_time=None, requests_since_reset=0):
    
    if last_reset_time and requests_since_reset >= 200:
        time_to_next_reset = 3600 - (time.time() - last_reset_time)
        print(f"Reached rate limit for this hour. Sleeping for {time_to_next_reset} seconds...")
        time.sleep(time_to_next_reset)
        last_reset_time = time.time()
        requests_since_reset = 0

    response = httpx.get(url, headers=headers, timeout=None)
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 30)) * (2 ** successive_429s)
        print(f"Encountered 429 Too Many Requests, sleeping for {retry_after} seconds")
        time.sleep(retry_after)
        return get_download_url(url, successive_429s + 1, last_reset_time, requests_since_reset)
    if response.status_code == 404:
        print(f"URL {url} returned 404, skipping.")
        mark_done(url)
        return None, last_reset_time, requests_since_reset
    if response.status_code == 504:
        print("Encountered 504 Gateway Timeout, trying again in 1 second...")
        time.sleep(1)
        return get_download_url(url, successive_429s, last_reset_time, requests_since_reset)
    elif response.status_code != 302:
        print(f"Download URL request returned code {response.status_code} instead of 302")
        return response.reason_phrase
    

    download_location = response.headers.get('location')
    if not download_location.startswith("https://"):
        raise ValueError(f"The Gods gave us a bad download location! {download_location}")

    if successive_429s > 0: # If there was a 429 response during this download attempt
        last_reset_time = time.time() # Reset the start time for the rate limit
        requests_since_reset = 0 # Reset the request counter

    return download_location, last_reset_time, requests_since_reset + 1



if __name__ == "__main__":
    last_reset_time = None
    requests_since_reset = 0
    for i, each in enumerate(get_urls(), 1):
        if check_done(each):
            continue
        current_time = datetime.now().strftime("%I:%M %p")
        print(f"\n\n[{i}] Downloading {each} at {current_time} ...")
        download_url, last_reset_time, requests_since_reset = get_download_url(each, last_reset_time=last_reset_time, requests_since_reset=requests_since_reset)

        downloaded_filename = download_from_url(download_url)
        if downloaded_filename is None:
            continue
        mark_done(each)
        print(f"Done with {os.path.basename(downloaded_filename)}!")

        sleep_duration = random.randint(5, 20)
        print(f"Sleeping for {sleep_duration} seconds before the next request...")
        time.sleep(sleep_duration)
    
        print("All downloads completed successfully! Press Enter to exit...")
        input()  # Wait for the user to press Enter before exiting







