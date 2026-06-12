"""
pdf_reader.py
Downloads a PDF from Google Drive and summarizes highlights using GPT-4o.
"""
from dotenv import load_dotenv
load_dotenv()
import re
import json
import tempfile
import requests
import pdfplumber
from openai import OpenAI

client = OpenAI()

SUMMARIZE_PROMPT = """You are reading a travel itinerary PDF.

Return ONLY a JSON object, no markdown, no explanation:
{
  "day_highlights": ["Day 1: Arrival, check-in hotel", "Day 2: ..."],
  "key_activities": ["Activity 1", "Activity 2"],
  "poster_highlights": ["3 to 5 most visually striking activities for a travel poster"]
}
"""


def download_pdf(download_url: str) -> str:
    """Download PDF from URL to temp file. Returns temp file path."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(download_url, headers=headers, timeout=20)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        raise ValueError("Google Drive returned HTML — file may require login or isn't publicly shared.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(response.content)
    tmp.close()
    return tmp.name


def extract_text(pdf_path: str) -> str:
    """Extract all text from PDF using pdfplumber."""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def summarize_itinerary(pdf_text: str) -> dict:
    """Summarize PDF text into structured highlights using GPT-4o."""
    truncated = pdf_text[:6000]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "user", "content": truncated}
        ],
        max_tokens=800,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()
    return json.loads(raw)


def enrich_from_drive_pdf(download_url: str) -> dict | None:
    """Full pipeline: download → extract → summarize. Returns None on failure."""
    try:
        print("⬇️  Downloading PDF...")
        pdf_path = download_pdf(download_url)

        print("📄 Extracting text...")
        text = extract_text(pdf_path)
        if not text.strip():
            print("⚠️  No extractable text in PDF.")
            return None

        print("🤖 Summarizing...")
        summary = summarize_itinerary(text)
        print("✅ PDF enrichment done.")
        return summary

    except Exception as e:
        print(f"❌ PDF enrichment failed: {e}")
        return None


# ── Demo ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    url = "https://drive.google.com/uc?export=download&id=1aBoWZMGy9qDv_FGIeyCRMfjrrEsli8Zc"
    result = enrich_from_drive_pdf(url)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
