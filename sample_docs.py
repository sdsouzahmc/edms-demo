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
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_supplier_invoice.png"),
        "TAX INVOICE", "INV-2026-7710", "25/09/2026", "Gulf Medical Supplies W.L.L.",
        "Invoice for Q3 laboratory consumables",
        ["Bill to: Finance Department", "", "Laboratory consumables delivered 14/09/2026 under purchase order",
         "PO-2026-0391. Payment is due within 30 days of invoice date.", "",
         "Total amount: QAR 36,450", "", "Please remit payment to the bank account on file.", "", "Accounts Receivable"]))
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_legal_contract.png"),
        "SERVICE AGREEMENT - DRAFT", "LEG-2026-0212", "18/09/2026", "Al Noor Facility Services",
        "Renewal of cleaning services contract",
        ["This agreement is entered into between the Hospital and the Contractor.", "",
         "The contract term is 24 months. Liability, indemnity and termination", "clauses are subject to review by legal counsel before signature.", "",
         "Contract value: QAR 215,000", "", "Governing law: State of Qatar.", "", "Legal & Contracts"]))
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_it_incident.png"),
        "IT SERVICE DESK - INCIDENT REPORT", "IT-2026-0933", "27/09/2026", "IT Service Desk",
        "Network outage - server room switch failure",
        ["Incident: core network switch in the server room failed at 02:14.", "",
         "Impact: EMR access degraded for 40 minutes. Backup firewall and", "server failover operated as designed.", "",
         "Action: replace switch, review system configuration and patch level.", "", "IT Infrastructure Team"]))
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_security_report.png"),
        "SECURITY - FIRE SAFETY INSPECTION", "SEC-2026-0075", "29/09/2026", "Security & Safety Office",
        "Fire safety drill and CCTV coverage review",
        ["The quarterly fire drill was completed in Block B. Evacuation time", "was 4 minutes 10 seconds.", "",
         "CCTV coverage gaps were identified at the east service entrance.", "Access card readers require firmware update.", "",
         "Recommended action: install two additional cameras.", "", "Security Office"]))
    samples.append(make_letter_image(
        os.path.join(ASSETS_DIR, "sample_clinical_referral.png"),
        "MEDICAL RECORDS - PATIENT REFERRAL", "MR-2026-5530", "30/09/2026", "Outpatient Clinic",
        "Patient referral and discharge summary request",
        ["Patient: Aisha M.   QID 2890*****14", "", "Admission 12/09/2026, discharge 19/09/2026. Please file the discharge", "summary in the patient medical record and send the clinical",
         "notes to the referring physician.", "", "Diagnosis and treatment plan attached.", "", "Medical Records Office"]))
    return samples


if __name__ == "__main__":
    print(generate_samples())
