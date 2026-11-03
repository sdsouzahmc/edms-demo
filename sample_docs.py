"""Generates realistic synthetic scanned-letter images for the OCR demo page,
and provides seed text content for the database seeding script."""
import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)


def _font(size=22, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def make_letter_image(path, title, ref, date, sender, subject, body_lines):
    img = Image.new("RGB", (900, 1150), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 899, 90], fill=(31, 56, 100))
    d.text((40, 30), title, font=_font(28, True), fill="white")
    y = 120
    for label, val in [("Ref No", ref), ("Date", date), ("From", sender), ("Subject", subject)]:
        d.text((40, y), f"{label}: {val}", font=_font(20, True), fill=(20, 20, 20))
        y += 34
    y += 20
    d.line([(40, y), (860, y)], fill=(200, 200, 200), width=2)
    y += 30
    for line in body_lines:
        d.text((40, y), line, font=_font(18), fill=(30, 30, 30))
        y += 30
    d.text((40, 1080), "Confidential Correspondence — Internal Use Only", font=_font(14), fill=(140, 140, 140))
    img.save(path)
    return path


def generate_samples():
    samples = []
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_regulatory_letter.png"),
        "MINISTRY OF PUBLIC HEALTH - QATAR",
        "MOPH-2026-4821", "15/09/2026", "Ministry of Public Health, Licensing Dept",
        "Annual Facility License Renewal Requirements",
        [
            "Dear Compliance Officer,",
            "",
            "This letter is to notify your facility of the annual licensing",
            "renewal requirements for the upcoming accreditation cycle.",
            "Please submit updated policy documentation, staff credentialing",
            "records, and facility inspection reports within 30 days of",
            "receipt of this notice.",
            "",
            "Amount: QAR 12,500 (Administrative renewal fee)",
            "",
            "Failure to comply within the stated period may result in",
            "suspension of operating license pending review.",
            "",
            "Regards,",
            "Licensing & Compliance Division",
        ]
    ))
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_hr_letter.png"),
        "INTERNAL MEMO - HUMAN RESOURCES",
        "HR-2026-1183", "02/09/2026", "HR Department",
        "Revised Staff Leave Policy",
        [
            "To: All Department Heads",
            "",
            "Please find attached the revised staff leave policy effective",
            "immediately. Key changes include updated annual leave accrual",
            "rates and a new process for emergency leave requests.",
            "",
            "All department heads are requested to acknowledge receipt and",
            "cascade this information to their teams within one week.",
            "",
            "Regards,",
            "Human Resources",
        ]
    ))
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_procurement_po.png"),
        "PURCHASE ORDER",
        "PO-2026-0417", "20/09/2026", "Procurement Department",
        "Medical Supplies - Q4 Replenishment",
        [
            "Supplier: Gulf Medical Supplies W.L.L.",
            "",
            "Please supply the items listed in the attached schedule as",
            "per the agreed framework contract pricing.",
            "",
            "Amount: QAR 48,900",
            "",
            "Delivery required by: 10/10/2026",
            "",
            "Regards,",
            "Procurement Department",
        ]
    ))
    return samples


if __name__ == "__main__":
    print(generate_samples())
