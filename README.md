# pythadex

Pythadex is a command line manga downloader which uses Mangadex's public api (https://api.mangadex.org)

As of right now it is in a crude state, however I plan to update it to be functional

Currently pythadex can
-----------------------
1. Download specific manga pages or chapters
2. Download an entire manga within it's own folder
3. Search for a manga with parameters specified (currently in a crude state)

Usage Information Which is Sent to Mangadex
-------------------------------------------
By default every download of a manga image using the python functions I've built sends a report to Mangadex. Essentially this information just contains what was downloaded and how long it took. Please leave this on as this is at Mangadex's request and it helps them monitor the health of their network. If you don't have much network bandwidth or you don't wish to send such data, feel free to turn it off.
