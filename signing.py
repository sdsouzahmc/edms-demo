"""E-signature (signature image + PIN) and digital signature (RSA-PSS over the document hash, X.509 certificate)."""
import base64
import hashlib
import io
import os
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

import db
import db_ext
import intake_ext as ix
import rfp_data

DEMO_PIN = "1234"
MEANINGS = {"approve": "Approved", "review": "Reviewed", "release": "Released"}


def _c():
    return db.get_conn()


def init():
    conn = _c()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS signing_ca (id INTEGER PRIMARY KEY CHECK (id=1), key_pem BLOB, cert_pem BLOB);
    CREATE TABLE IF NOT EXISTS user_signatures (
        user TEXT PRIMARY KEY, image BLOB, kind TEXT, pin_salt TEXT, pin_hash TEXT,
        key_pem BLOB, cert_pem BLOB, serial TEXT, valid_to TEXT, created_at TEXT, updated_at TEXT, is_demo INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS doc_signatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER, signer TEXT, role TEXT, stage TEXT, meaning TEXT,
        on_behalf_of TEXT, content_hash TEXT, signature TEXT, cert_serial TEXT, signed_at TEXT, image BLOB);
    """)
    conn.commit()
    conn.close()


def _h(s, salt):
    return hashlib.sha256((salt + s).encode()).hexdigest()


def _utc():
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ CA / certs --
def _ca():
    conn = _c()
    r = conn.execute("SELECT * FROM signing_ca WHERE id=1").fetchone()
    if r:
        conn.close()
        return (serialization.load_pem_private_key(r["key_pem"], None), x509.load_pem_x509_certificate(r["cert_pem"]))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EDMS Demo"), x509.NameAttribute(NameOID.COMMON_NAME, "EDMS Demo Certificate Authority")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(_utc() - timedelta(days=1)).not_valid_after(_utc() + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).sign(key, hashes.SHA256()))
    conn.execute("INSERT INTO signing_ca (id, key_pem, cert_pem) VALUES (1,?,?)",
                 (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
                  cert.public_bytes(serialization.Encoding.PEM)))
    conn.commit()
    conn.close()
    return key, cert


def typed_signature_png(name):
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"):
        if os.path.exists(p):
            font = ImageFont.truetype(p, 64)
            break
    font = font or ImageFont.load_default()
    img = Image.new("RGBA", (640, 150), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.text((20, 30), name, font=font, fill=(20, 40, 110, 255))
    d.line((20, 118, 560, 108), fill=(20, 40, 110, 160), width=3)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def clean_signature_image(data):
    """Make white paper transparent and crop, so an uploaded/scanned signature can be stamped on a document."""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    im.thumbnail((900, 300))
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            lum = (r + g + b) / 3
            if lum > 215:
                px[x, y] = (255, 255, 255, 0)
            else:
                px[x, y] = (min(r, 60), min(g, 70), max(b, 110) if lum < 180 else b, 255)
    bbox = im.getbbox()
    if bbox:
        im = im.crop(bbox)
    bio = io.BytesIO()
    im.save(bio, format="PNG")
    return bio.getvalue()


def enroll(user, image_png, kind, pin, demo=False):
    """Create (or replace) the user's signature image, PIN and key pair / certificate."""
    ca_key, ca_cert = _ca()
    prof = rfp_data.ROLES.get(user, {"role": "User", "dept": "EDMS"})
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, user), x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, prof["dept"]),
                      x509.NameAttribute(NameOID.TITLE, prof["role"]), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "EDMS Demo")])
    until = _utc() + timedelta(days=730)
    cert = (x509.CertificateBuilder().subject_name(subj).issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(_utc() - timedelta(days=1)).not_valid_after(until)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(ca_key, hashes.SHA256()))
    salt = os.urandom(8).hex()
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(pin.encode()))
    now = db.now()
    conn = _c()
    conn.execute("""INSERT OR REPLACE INTO user_signatures (user, image, kind, pin_salt, pin_hash, key_pem, cert_pem, serial, valid_to,
                    created_at, updated_at, is_demo) VALUES (?,?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM user_signatures WHERE user=?),?),?,?)""",
                 (user, image_png, kind, salt, _h(pin, salt), pem, cert.public_bytes(serialization.Encoding.PEM), f"{cert.serial_number:X}"[:20],
                  until.strftime("%Y-%m-%d"), user, now, now, 1 if demo else 0))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Signature Enrolled" if not demo else "Demo Signature Provisioned",
                 f"{kind} signature + digital certificate issued (serial {cert.serial_number:X}"[:90] + ")")


def profile(user):
    conn = _c()
    r = conn.execute("SELECT * FROM user_signatures WHERE user=?", (user,)).fetchone()
    conn.close()
    return dict(r) if r else None


def ensure(user):
    """Demo convenience: every demo user gets a typed signature and PIN 1234 on first use (replaceable with a real upload)."""
    p = profile(user)
    if not p:
        enroll(user, typed_signature_png(user), "typed", DEMO_PIN, demo=True)
        p = profile(user)
    return p


def check_pin(user, pin):
    p = profile(user)
    return bool(p) and _h(pin or "", p["pin_salt"]) == p["pin_hash"]


def change_pin(user, old, new):
    p = profile(user)
    key = serialization.load_pem_private_key(p["key_pem"], old.encode())
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(new.encode()))
    salt = os.urandom(8).hex()
    conn = _c()
    conn.execute("UPDATE user_signatures SET key_pem=?, pin_salt=?, pin_hash=?, is_demo=0, updated_at=? WHERE user=?", (pem, salt, _h(new, salt), db.now(), user))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Signature PIN Changed", "")


def replace_image(user, png, kind):
    conn = _c()
    conn.execute("UPDATE user_signatures SET image=?, kind=?, is_demo=0, updated_at=? WHERE user=?", (png, kind, db.now(), user))
    conn.commit()
    conn.close()
    db.log_audit(None, user, "Signature Image Updated", kind)


# ------------------------------------------------------------------- signing ---
def content_hash(doc_id):
    d = db.get_document(doc_id)
    shas = sorted(f["sha"] for f in _files(doc_id))
    raw = "|".join([d["doc_code"], d["title"] or "", str(d["current_version"]), d["body_text"] or "", *shas])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _files(doc_id):
    conn = _c()
    rows = conn.execute("SELECT sha FROM correspondence_files WHERE document_id=?", (doc_id,)).fetchall()
    conn.close()
    return rows


def sign(doc_id, user, stage, pin, meaning="Approved", on_behalf_of=None):
    """Returns (ok, message_or_id)."""
    p = ensure(user)
    if not check_pin(user, pin):
        db.log_audit(doc_id, user, "E-Signature Failed", f"wrong PIN at stage {stage}", "Denied")
        return False, "Incorrect signature PIN."
    key = serialization.load_pem_private_key(p["key_pem"], pin.encode())
    ch = content_hash(doc_id)
    sig = key.sign(bytes.fromhex(ch), padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
    conn = _c()
    cur = conn.execute("""INSERT INTO doc_signatures (document_id, signer, role, stage, meaning, on_behalf_of, content_hash, signature, cert_serial, signed_at, image)
                          VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                       (doc_id, user, rfp_data.ROLES.get(user, {}).get("role", ""), stage, meaning, on_behalf_of, ch,
                        base64.b64encode(sig).decode(), p["serial"], db.now(), p["image"]))
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    short = db_ext.log_esign(doc_id, user, stage)
    db.log_audit(doc_id, user, "Digitally Signed", f"{meaning} · stage {stage} · RSA-2048/SHA-256 · cert {p['serial']} · hash {ch[:12]}…"
                 + (f" · on behalf of {on_behalf_of}" if on_behalf_of else ""))
    return True, {"id": sid, "short": short, "hash": ch}


def signatures(doc_id=None, user=None):
    conn = _c()
    q, p = "SELECT s.*, d.doc_code, d.title FROM doc_signatures s JOIN documents d ON d.id=s.document_id WHERE 1=1", []
    if doc_id:
        q += " AND s.document_id=?"
        p.append(doc_id)
    if user:
        q += " AND s.signer=?"
        p.append(user)
    rows = [dict(r) for r in conn.execute(q + " ORDER BY s.id DESC", p).fetchall()]
    conn.close()
    return rows


def verify(sig_row):
    """Returns (status, detail). status: Valid | Document changed | Invalid"""
    p = profile(sig_row["signer"])
    if not p:
        return "Invalid", "signer certificate not found"
    ca_key, ca_cert = _ca()
    cert = x509.load_pem_x509_certificate(p["cert_pem"])
    try:
        ca_cert.public_key().verify(cert.signature, cert.tbs_certificate_bytes, padding.PKCS1v15(), cert.signature_hash_algorithm)
    except Exception:
        return "Invalid", "certificate not issued by the EDMS CA"
    if cert.serial_number != int(p["serial"], 16) and f"{cert.serial_number:X}"[:20] != sig_row["cert_serial"]:
        return "Invalid", "certificate does not match the signature"
    try:
        cert.public_key().verify(base64.b64decode(sig_row["signature"]), bytes.fromhex(sig_row["content_hash"]),
                                 padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
    except Exception:
        return "Invalid", "signature does not match"
    if content_hash(sig_row["document_id"]) != sig_row["content_hash"]:
        return "Document changed", "the document was modified or a new version was created after this signature"
    return "Valid", "signature and document content verified"


def certificate_info(user):
    p = profile(user)
    if not p:
        return None
    c = x509.load_pem_x509_certificate(p["cert_pem"])
    return {"subject": c.subject.rfc4514_string(), "issuer": c.issuer.rfc4514_string(), "serial": f"{c.serial_number:X}",
            "from": c.not_valid_before_utc.strftime("%Y-%m-%d"), "to": c.not_valid_after_utc.strftime("%Y-%m-%d"),
            "key": f"RSA-{c.public_key().key_size}", "alg": "SHA-256 with RSA-PSS",
            "fingerprint": c.fingerprint(hashes.SHA256()).hex().upper()[:32], "pem": p["cert_pem"]}


# ----------------------------------------------------------------- signed PDF --
def signed_pdf(doc_id):
    import fitz
    import exchange as ex
    d = db.get_document(doc_id)
    base, _ = ex.controlled_copy(doc_id, {"recipient_name": "", "token_hint": "", "watermark": 0})
    pdf = fitz.open(stream=base, filetype="pdf")
    sigs = list(reversed(signatures(doc_id)))
    pg = pdf.new_page()
    pg.insert_text((50, 60), "Signature page", fontsize=16)
    pg.insert_text((50, 80), ex._latin(f"{d['doc_code']} - {d['title']}"), fontsize=9.5)
    y = 110
    for s in sigs:
        if y > 700:
            pg = pdf.new_page()
            y = 60
        status, _ = verify(s)
        col = (0.1, 0.45, 0.15) if status == "Valid" else (0.7, 0.4, 0.0)
        pg.draw_rect(fitz.Rect(45, y - 6, 550, y + 92), color=(0.8, 0.82, 0.86), width=0.8)
        try:
            pg.insert_image(fitz.Rect(55, y, 195, y + 52), stream=s["image"], keep_proportion=True)
        except Exception:
            pass
        who = s["signer"] + (f" (on behalf of {s['on_behalf_of']})" if s["on_behalf_of"] else "")
        pg.insert_text((210, y + 12), ex._latin(f"{s['meaning']} - {s['stage']}"), fontsize=10.5)
        pg.insert_text((210, y + 27), ex._latin(f"{who}, {s['role']}"), fontsize=9)
        pg.insert_text((210, y + 41), f"Signed {s['signed_at']}  |  Certificate {s['cert_serial']}", fontsize=8)
        pg.insert_text((210, y + 54), f"SHA-256 {s['content_hash'][:48]}...", fontsize=7)
        pg.insert_text((55, y + 76), f"Digital signature: {status}", fontsize=8.5, color=col)
        y += 108
    pg.insert_text((50, 800), "Digitally signed with RSA-2048 / SHA-256 (EDMS Demo CA). Verify in EDMS > My Signature > Verify.", fontsize=7, color=(0.4, 0.4, 0.4))
    out = pdf.tobytes(garbage=3, deflate=True)
    pdf.close()
    return out
