"""Real OCR helpers (Tesseract, English + Arabic) and lightweight metadata extraction."""
import re
import io
from PIL import Image
import pytesseract


def run_ocr(image: Image.Image, lang="eng+ara"):
    """Returns extracted text using real Tesseract OCR."""
    return pytesseract.image_to_string(image, lang=lang)


def extract_metadata(text: str) -> dict:
    """Very small heuristic metadata extractor over OCR'd / typed text."""
    meta = {}
    code = re.search(r"\b[A-Z]{2,6}-\d{4}-\d{2,6}\b", text)
    if code:
        meta["Reference Number"] = code.group(0)
    date = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b", text)
    if date:
        meta["Date"] = date.group(1)
    sender = re.search(r"(?:From|Sender)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if sender:
        meta["Sender"] = sender.group(1).strip().splitlines()[0]
    subj = re.search(r"(?:Subject|Re)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if subj:
        meta["Subject"] = subj.group(1).strip().splitlines()[0]
    amount = re.search(r"(?:QAR|Amount)\s*[:\-]?\s*([\d,]+(?:\.\d{2})?)", text, re.IGNORECASE)
    if amount:
        meta["Amount (QAR)"] = amount.group(1)
    return meta


def auto_name(meta: dict, fallback: str) -> str:
    if "Reference Number" in meta:
        return meta["Reference Number"]
    if "Subject" in meta:
        return meta["Subject"][:60]
    return fallback
