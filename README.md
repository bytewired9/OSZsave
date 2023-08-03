# OSZsave

# Instructions for osu! Beatmap Downloader

## Getting Headers:
1. Go to [osu.ppy.sh](https://osu.ppy.sh).
2. Go to the beatmaps page.
3. Go to a random beatmap.
4. Open the network page (press `F12` or right-click the page and select 'Inspect', then go to the 'Network' tab).
5. Click the download button on the beatmap (note: you don't have to save it, just click).
6. Find the packet that is titled "download."
7. Right-click it and choose 'Copy as cURL (bash).'
8. Paste that into `curl_command.txt`.

## Getting Beatmap Links:
1. Go to [osu.ppy.sh](https://osu.ppy.sh).
2. Go to your desired user profile.
3. Open your browser's JS console window (press `F12` or right-click the page and select 'Inspect', then go to the 'Console' tab).
4. Paste the script from `script.js` into there.
5. Let it run.
6. Once it is finished you will have a list of beatmap links, paste them into `beatmap_links.json`.

## Running:
- Once all of these are done, run the program.

## Importing Beatmaps:
1. Once all of the beatmaps have finished downloading, open osu!
2. Make sure osu is not in fullscreen mode.
3. Select all the files from the 'downloaded' folder and drag them into the osu! window.
4. Enjoy the maps.

## Note on Runtime:
- Please be aware that the program could take up to several hours to complete if you are processing a large list of beatmaps. Make sure to plan accordingly and be patient.

## Need Help?
- If you encounter any problems or have any questions about the process, feel free to reach out to me on Discord: @forgedcore8. I'll be happy to assist you!
