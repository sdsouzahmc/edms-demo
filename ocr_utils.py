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
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    def after_label(label):
        for i, l in enumerate(lines[:-1]):
            if re.fullmatch(label + r"\s*[:\-]?", l, re.IGNORECASE):
                return lines[i + 1]
        return None
    if "Subject" not in meta and after_label("Subject"):
        meta["Subject"] = after_label("Subject")
    if "Sender" not in meta and after_label("From"):
        meta["Sender"] = after_label("From")
    if lines and 3 <= len(lines[0]) <= 60 and not re.fullmatch(r"[\d\W]+", lines[0]):
        meta["Heading"] = lines[0]
    amount = re.search(r"(?:QAR|Amount)\s*[:\-]?\s*([\d,]+(?:\.\d{2})?)", text, re.IGNORECASE)
    if amount:
        meta["Amount (QAR)"] = amount.group(1)
    return meta


def _pretty(s: str) -> str:
    s = re.sub(r"^\d{1,3}[_\-. ]+", "", s or "")
    return re.sub(r"\s+", " ", s.replace("_", " ")).strip()


def auto_name(meta: dict, fallback: str) -> str:
    """Readable title: 'Subject (Ref)', else 'Heading (Ref)', else the reference, else a tidied file name."""
    ref = meta.get("Reference Number")
    head = meta.get("Subject") or meta.get("Heading")
    if head and ref:
        return f"{head[:55]} ({ref})"
    if head:
        return head[:70]
    if ref:
        return ref
    return _pretty(fallback)
