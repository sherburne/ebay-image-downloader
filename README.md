# eBay Image Downloader

This script downloads the main images from a list of eBay listings (URLs stored in `gallery.json`).  
It uses Playwright to load each eBay page, scrapes the primary product image (using multiple strategies), and saves each image to disk, organized by folders.

- **Input:** A JSON file (`gallery.json`) listing eBay item URLs and info.
- **Output:** Images saved in `ebay_by_title/<folder>/<id>.jpg` and a summary JSON (`gallery_test5.json`) with successfully processed items.

**Requirements:**  
- Python 3.8+
- `playwright` (`pip install playwright && playwright install`)

**Usage:**  
1. Edit `gallery.json` with your items (must include `"ebay_url"` and `"regex"` for each). The script will download images with a matching `alt` attribute.
2. Run the script: `python download_ebay_images.py`
3. Check images and results in the output folder!

---

## How it works

- Loads each eBay URL in a headless browser.
- Tries to extract the main image from meta tags or main image tags.
- Saves the highest-resolution version possible.
- Folders and filenames are auto-generated from the input data.

---

**Note:**  
For large galleries or frequent use, consider adding error handling for network issues, rate limits, or eBay layout changes.

