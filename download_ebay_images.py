"""
download_ebay_images.py

Downloads images from eBay listings where alt tags match a regex pattern.
Saves images into organized folders using item number and sequential numbering.
Crawls through the listing's image carousel.

Usage:
    python download_ebay_images.py --input gallery.json --output gallery-output.json --img_root gallery
"""

import json
import os
import asyncio
import argparse
import re
from typing import Optional, Dict, List, Any, Tuple
from playwright.async_api import async_playwright, Page


async def get_matching_images(page: Page, ebay_url: str, regex_pattern: str) -> List[Tuple[str, str]]:
    """
    Extracts all images from eBay carousel where alt tags match the regex pattern.

    Args:
        page (Page): Playwright page object.
        ebay_url (str): The URL of the eBay item.
        regex_pattern (str): Regular expression to match against alt attributes.

    Returns:
        List[Tuple[str, str]]: List of (image_url, alt_text) tuples for matching images.
    """
    await page.goto(ebay_url, timeout=60000)
    await page.wait_for_timeout(2500)
    
    try:
        # Compile regex pattern
        pattern = re.compile(regex_pattern)
    except re.error as e:
        print(f"  [!] Invalid regex pattern: {regex_pattern} - {e}")
        return []
    
    matching_images: List[Tuple[str, str]] = []
    seen_alts = set()  # Track seen alt texts to avoid duplicates
    
    # Try multiple selectors to find carousel images
    # eBay uses various selectors for gallery images
    selectors = [
        "img[alt]",  # All images with alt tags
        "#vi_main_img_fs img",  # Images in main gallery
        ".vi-image-carousel img",  # Carousel images
        "#vi_main_img_fs_slider img",  # Slider images
        ".vi-image-carousel-list img",  # Carousel list images
    ]
    
    for selector in selectors:
        try:
            img_elements = await page.locator(selector).all()
            for img in img_elements:
                try:
                    alt_text = await img.get_attribute("alt")
                    if not alt_text:
                        continue
                    
                    # Check if alt matches regex
                    if pattern.search(alt_text):
                        # Get image URL - try src first, then data-src, then srcset
                        img_url = await img.get_attribute("src")
                        if not img_url or img_url.startswith("data:"):
                            img_url = await img.get_attribute("data-src")
                        if not img_url or img_url.startswith("data:"):
                            srcset = await img.get_attribute("srcset")
                            if srcset:
                                # Extract first URL from srcset
                                img_url = srcset.split(",")[0].strip().split()[0]
                        
                        if img_url and img_url not in [url for url, _ in matching_images]:
                            # Try to upgrade to highest resolution
                            if "s-l" in img_url:
                                img_url = img_url.replace("s-l500", "s-l1600").replace("s-l1200", "s-l1600").replace("s-l300", "s-l1600")
                            
                            # Avoid duplicates based on alt text
                            if alt_text not in seen_alts:
                                matching_images.append((img_url, alt_text))
                                seen_alts.add(alt_text)
                except Exception as e:
                    continue
        except Exception as e:
            continue
    
    # If no matches found with specific selectors, try a broader approach
    if not matching_images:
        try:
            all_imgs = await page.locator("img").all()
            for img in all_imgs:
                try:
                    alt_text = await img.get_attribute("alt")
                    if not alt_text:
                        continue
                    
                    if pattern.search(alt_text):
                        img_url = await img.get_attribute("src")
                        if not img_url or img_url.startswith("data:"):
                            img_url = await img.get_attribute("data-src")
                        
                        if img_url and not img_url.startswith("data:"):
                            if "s-l" in img_url:
                                img_url = img_url.replace("s-l500", "s-l1600").replace("s-l1200", "s-l1600").replace("s-l300", "s-l1600")
                            
                            if alt_text not in seen_alts:
                                matching_images.append((img_url, alt_text))
                                seen_alts.add(alt_text)
                except Exception:
                    continue
        except Exception:
            pass
    
    return matching_images


def extract_item_number(ebay_url: str) -> Optional[str]:
    """
    Extracts the item number from an eBay URL.

    Args:
        ebay_url (str): The eBay item URL.

    Returns:
        Optional[str]: The item number if found, otherwise None.
    """
    # eBay URLs typically have format: https://www.ebay.com/itm/ITEM_NUMBER
    # or https://www.ebay.com/itm/ITEM_NUMBER?...
    match = re.search(r'/itm/(\d+)', ebay_url)
    if match:
        return match.group(1)
    return None


async def download_image(page: Page, img_url: str, save_path: str) -> bool:
    """
    Downloads an image from the given URL using Playwright.

    Args:
        page (Page): Playwright page object.
        img_url (str): Image URL.
        save_path (str): Local file path to save the image.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        img_resp = await page.goto(img_url)
        if not img_resp:
            return False
        img_bytes = await img_resp.body()
        with open(save_path, "wb") as f:
            f.write(img_bytes)
        return True
    except Exception as e:
        print(f"  [!] Exception: {e} for {img_url}")
        return False


async def process_gallery(
    input_file: str, output_file: str, img_root: str
) -> None:
    """
    Loads the gallery JSON, downloads images matching regex patterns, and saves the results.

    Args:
        input_file (str): Path to input JSON.
        output_file (str): Path to output JSON.
        img_root (str): Root directory for images.
    """
    with open(input_file, encoding="utf-8") as f:
        gallery = json.load(f)

    output: List[Dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for item in gallery:
            ebay_url = item.get("ebay_url", "")
            regex_pattern = item.get("regex", "")
            
            if not ebay_url:
                print(f"  [!] Skipping item missing ebay_url: {item}")
                continue
            
            if not regex_pattern:
                print(f"  [!] Skipping item missing regex pattern: {ebay_url}")
                continue
            
            # Extract item number from URL
            item_number = extract_item_number(ebay_url)
            if not item_number:
                print(f"  [!] Could not extract item number from URL: {ebay_url}")
                continue
            
            print(f"Processing: {ebay_url}")
            print(f"  Item number: {item_number}")
            print(f"  Regex: {regex_pattern}")
            
            matching_images = await get_matching_images(page, ebay_url, regex_pattern)
            
            if not matching_images:
                print(f"  [!] No matching images found for: {ebay_url}")
                continue
            
            print(f"  [*] Found {len(matching_images)} matching image(s)")
            
            # Create folder named after item number
            folder_path = os.path.join(img_root, item_number)
            os.makedirs(folder_path, exist_ok=True)
            
            downloaded_files: List[str] = []
            skipped_files: List[str] = []
            
            # Download images with sequential numbering
            for idx, (img_url, alt_text) in enumerate(matching_images, start=1):
                # Generate filename: item_number - sequential number (001, 002, 003, ...)
                seq_num = f"{idx:03d}"
                img_fn = f"{item_number}-{seq_num}.jpg"
                img_fp = os.path.join(folder_path, img_fn)
                
                # Check if file already exists
                if os.path.exists(img_fp):
                    print(f"  [*] Skipping existing image: {img_fn} (alt: {alt_text[:50]}...)")
                    skipped_files.append(img_fn)
                    continue
                
                print(f"  [*] Downloading: {img_fn} (alt: {alt_text[:50]}...)")
                success = await download_image(page, img_url, img_fp)
                
                if success:
                    downloaded_files.append(img_fn)
                    print(f"  [*] Image saved: {img_fp}")
                else:
                    print(f"  [!] Failed to download image: {img_url}")
            
            # Add item to output with downloaded files info
            if downloaded_files or skipped_files:
                output_item = item.copy()
                output_item["downloaded_files"] = downloaded_files
                output_item["skipped_files"] = skipped_files
                output_item["total_matched"] = len(matching_images)
                output.append(output_item)
        
        await browser.close()

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nAll done! See {output_file} and images in {img_root}/")


def parse_args():
    parser = argparse.ArgumentParser(description="Download images from eBay listings matching regex patterns on alt tags.")
    parser.add_argument("--input", default="gallery.json", help="Input JSON file (default: gallery.json)")
    parser.add_argument("--output", default="gallery-output.json", help="Output JSON file (default: gallery-output.json)")
    parser.add_argument("--img_root", default="gallery", help="Root folder to save images (default: gallery)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(process_gallery(args.input, args.output, args.img_root))
