"""
promo_parser.py
Detects Google Drive links from raw promo text.
Caption is kept identical to input + phone number appended.
Poster text has provider CTA lines stripped.
"""

import re


def convert_drive_link(url: str) -> str | None:
    """Convert Google Drive share link to direct download URL."""
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return None


def parse_promo(raw_text: str) -> dict:
    """
    Extract Drive links from raw promo text.
    Returns:
    - whatsapp_caption: original text + phone number
    - poster_text: cleaned text without provider CTA lines
    - drive_links: list of {original_url, download_url} dicts
    """
    # Find all Google Drive links
    drive_pattern = r"https://drive\.google\.com/file/d/[a-zA-Z0-9_-]+[^\s]*"
    found_links = re.findall(drive_pattern, raw_text)

    drive_links = []
    for url in found_links:
        download_url = convert_drive_link(url)
        if download_url:
            drive_links.append({
                "original_url": url,
                "download_url": download_url
            })

    # WhatsApp caption = raw text as-is + your phone number
    caption = raw_text.strip() + "\n📞 WA 0817771667"

    # Clean text for poster prompt — strip provider's generic CTA lines
    cleaned = re.sub(r"(?i)hubungi travel agent.*", "", raw_text)
    cleaned = re.sub(r"(?i)segera hubungi.*", "", cleaned)
    cleaned = re.sub(r"(?i)📩.*sebelum kehabisan.*", "", cleaned)
    cleaned = re.sub(r"(?i)hubungi.*agen.*sekarang.*", "", cleaned)
    cleaned = cleaned.strip()

    return {
        "whatsapp_caption": caption,
        "poster_text": cleaned,
        "drive_links": drive_links,
    }


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = """✨ BEST SAVER KUNMING ✨
2 Rute Favorit dengan harga SUPER HEMAT untuk liburan seru ke China 🇨🇳❄️
📅 SPECIAL DATE : 20 & 27 JUNI 2026
💰 START FROM IDR 6.990.000
Link Itinerary
https://drive.google.com/file/d/1QGgZpxx11MTSQTDGeMVCDfOOhCKTNa07/view?usp=drive_link
🔥 Seat terbatas!
📩 Hubungi travel agent langganan Anda sekarang sebelum kehabisan seat."""

    result = parse_promo(sample)
    print("Caption:\n", result["whatsapp_caption"])
    print("\nPoster text:\n", result["poster_text"])
    print("\nDrive links:", result["drive_links"])