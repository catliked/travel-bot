"""
main.py
Travel Bot - Telegram bot for travel promo automation.

Flow:
- You send promo text → bot returns identical WhatsApp caption + your number + ChatGPT image prompt
- If Drive link detected → bot asks if you want PDF enrichment
- You send poster image back → bot stamps logo → returns final poster

Environment variables required:
- TELEGRAM_BOT_TOKEN
- OPENAI_API_KEY
"""

import os
import logging
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from PIL import Image

from promo_parser import parse_promo
from pdf_reader import enrich_from_drive_pdf

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"

POSTER_INSTRUCTION = (
    "\n\n---\n"
    "Make this into a professional travel agency promo poster, size 2:3. "
    "Use high quality cinematic photorealistic style. "
    "Top right corner must have a clean plain background area — "
    "no text, no subjects, no busy details — so a logo can be stamped there later. "
    "Corporate travel agency Instagram post style, visually striking."
)


# ── Logo Stamper ──────────────────────────────────────────────────────────────

def stamp_logo(image_bytes: bytes) -> bytes:
    """Stamp logo onto top-right corner of poster. Returns stamped PNG bytes."""
    poster = Image.open(BytesIO(image_bytes)).convert("RGBA")
    poster_w, poster_h = poster.size

    logo = Image.open(LOGO_PATH).convert("RGBA")

    # Resize logo to 15% of poster width
    target_w = int(poster_w * 0.40)
    ratio = target_w / logo.width
    target_h = int(logo.height * ratio)
    logo = logo.resize((target_w, target_h), Image.LANCZOS)

    # Paste top-right with 24px margin
    margin = 24
    x = poster_w - target_w - margin
    y = margin
    poster.paste(logo, (x, y), logo)

    output = BytesIO()
    poster.convert("RGB").save(output, format="PNG")
    return output.getvalue()


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming promo text."""
    raw_text = update.message.text.strip()

    # Parse — extract drive links, build caption
    data = parse_promo(raw_text)

    # Store for later use
    context.user_data["raw_text"] = raw_text
    context.user_data["data"] = data
    context.user_data["pdf_enrichment"] = None

    # Store caption for sending after poster stamp
    context.user_data["whatsapp_caption"] = data["whatsapp_caption"]

    # If Drive links found, ask about PDF
    if data.get("drive_links"):
        keyboard = [
            [
                InlineKeyboardButton("✅ Ya, include PDF", callback_data="pdf_yes"),
                InlineKeyboardButton("⏭ Skip", callback_data="pdf_skip"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        count = len(data["drive_links"])
        await update.message.reply_text(
            f"📋 {count} itinerary PDF ditemukan. Mau include detail dari PDF untuk poster?",
            reply_markup=reply_markup
        )
    else:
        # No PDF, send image prompt immediately
        await send_image_prompt(update.message, raw_text, None)


async def send_image_prompt(message, raw_text: str, pdf_enrichment: dict | None):
    """Sends the ChatGPT image prompt."""
    extra = ""
    if pdf_enrichment and pdf_enrichment.get("poster_highlights"):
        highlights = ", ".join(pdf_enrichment["poster_highlights"])
        extra = f"\n\nKey visual highlights: {highlights}"

    prompt = f"{raw_text.strip()}{extra}{POSTER_INSTRUCTION}"

    await message.reply_text(
        f"🎨 *ChatGPT Image Prompt:*\n\n`{prompt}`",
        parse_mode="Markdown"
    )
    await message.reply_text(
        "👆 Paste ke ChatGPT → save poster → kirim balik ke sini untuk stamp logo! 🖼️"
    )


async def handle_pdf_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles PDF yes/no inline button."""
    query = update.callback_query
    await query.answer()

    raw_text = context.user_data.get("raw_text", "")
    data = context.user_data.get("data", {})

    if query.data == "pdf_yes":
        await query.edit_message_text("⬇️ Downloading & reading PDF...")

        # Use first drive link found
        first_link = data["drive_links"][0]
        enrichment = enrich_from_drive_pdf(first_link["download_url"])
        context.user_data["pdf_enrichment"] = enrichment

        if enrichment:
            highlights = "\n".join(f"• {h}" for h in enrichment.get("poster_highlights", []))
            await query.message.reply_text(f"✅ PDF read! Top highlights:\n{highlights}")
        else:
            await query.message.reply_text("⚠️ Couldn't read PDF — continuing without it.")
    else:
        await query.edit_message_text("⏭ Skipping PDF.")

    enrichment = context.user_data.get("pdf_enrichment")
    await send_image_prompt(query.message, raw_text, enrichment)


async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming poster image — stamps logo and sends back."""
    await update.message.reply_text("🖼️ Stamping logo...")

    if not LOGO_PATH.exists():
        await update.message.reply_text(
            "❌ Logo not found! Make sure assets/logo.png exists."
        )
        return

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        stamped = stamp_logo(bytes(image_bytes))

        # Send poster
        await update.message.reply_photo(photo=BytesIO(stamped))
        # Send caption right after
        caption = context.user_data.get("whatsapp_caption", "")
        if caption:
            await update.message.reply_text(caption)

    except Exception as e:
        await update.message.reply_text(f"❌ Stamping failed: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(handle_pdf_callback, pattern="^pdf_"))

    print("🤖 Travel bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()