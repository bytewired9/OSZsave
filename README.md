<div align=center>
    
# OSZsave - osu! Beatmap Downloader
    
<img src="readme/oszsave.png"
           alt="OSZsave logo"
             style="height: 300px; width: auto;" />
             
[![Button Icon]][Link]

[Button Icon]: https://img.shields.io/badge/Installation-0b5394?style=for-the-badge&logoColor=white&logo=DocuSign

[Link]: https://github.com/ForgedCore8/OSZsave/releases/latest/download/oszsave.exe

![GitHub all releases](https://img.shields.io/github/downloads/ForgedCore8/OSZsave/total) ![GitHub](https://img.shields.io/github/license/ForgedCore8/OSZsave) [![Try it on gitpod](https://img.shields.io/badge/try-on%20gitpod-brightgreen.svg)](https://gitpod.io/#https://github.com/ForgedCore8/OSZsave)

![Alt](https://repobeats.axiom.co/api/embed/1da7c935726e07d16ffc00d3ab4287d8afa5f817.svg "Repobeats analytics image")
</div>
   
## About

OSZsave is a powerful and convenient tool designed to help osu! players download their favorite beatmaps in bulk. Whether you want to import a handful or hundreds of beatmaps from user profiles, OSZsave streamlines the process, saving you time and effort.

### Features
- **Bulk Download**: Easily download multiple beatmaps at once from your chosen user profile.
- **Custom Headers**: Personalize your download process by adding custom headers.
- **Ease of Use**: Simple step-by-step instructions guide you through the setup and download process.
- **Lightweight**: OSZsave is designed to be user-friendly, lightweight, and efficient, making it accessible to players of all skill levels.
- **Anti Ratelimit**: Avoiding the rate limit to download as many beatmaps as possible.
- **Wide Range**: Unlike other tools, this program allows you to get every beatmap from a user's profile.
- **Storage Efficient**: This tool ensures that it is only downloading new maps, saving you space and time.

### Why OSZsave?
osu! is a fast-paced rhythm game with a vibrant community that continually creates new beatmaps. OSZsave provides a way to quickly and easily download these beatmaps, whether you're looking to experiment with new challenges or simply expand your collection. With its emphasis on user-friendliness and efficiency, OSZsave is a must-have tool for osu! enthusiasts.

<img src="readme/OSZbanner-lite.png"
           alt="OSZ Banner"/>
<div align=center>
    
# Instructions:
</div>

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


# Console Script for getting beatmap list:
```js
let paydirt = [];
let targets = ["play-detail__title", "beatmapset-panel__main-link", "profile-extra-entries__text", "beatmap-playcount__title"];

function findNextButtons() {
    console.log("Searching for 'next' buttons...");
    let btn = document.getElementsByClassName("show-more-link--profile-page")[0];
    if (btn) {
        console.log("Found a 'next' button, clicking...");
        btn.scrollIntoView({ behavior: "auto", block: "center" }); 
        btn.click();
        setTimeout(findNextButtons, 1000);
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
            link.scrollIntoView({ behavior: "auto", block: "center" }); 
            paydirt.push(newUrl);
            await new Promise(resolve => setTimeout(resolve, 10)); 
        }
    }

    console.log("End collecting URLs...");
    processPaydirt();
}

function processPaydirt() {
    console.log("Gold digging completed, processing URLs...");
    let paydirtModified = paydirt.map(url => {
        let match = url.match(/\/b\/([0-9]+)\?[A-Za-z]=[0-9]+/);
        if (match) {
            return `https://osu.ppy.sh/beatmapsets/${match[1]}/download`;
        } else if (url.match(/https:\/\/osu\.ppy\.sh\/beatmapsets\/[0-9]+$/)) {
            return url + "/download"; 
        } else {
            return url.replace(/#[A-Za-z]+\/[0-9]+/g, '/download');
        }
    });

    let uniquePaydirt = [...new Set(paydirtModified)]; 
    console.log("Final processed list of URLs:");
    console.log(JSON.stringify(uniquePaydirt, null, 4));
}


console.log("Script started...");
findNextButtons();
```

---

## Need Help?
- If you encounter any problems or have any questions about the process, feel free to reach out to me on Discord: @forgedcore8. I'll be happy to assist you!
- Alternatively, you can also go to the project's [issue tracker](https://github.com/ForgedCore8/OSZsave/issues)

