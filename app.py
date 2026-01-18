from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import csv
import io
import re
import zipfile

app = FastAPI(title="Lead Filter API", version="5.1")

# =====================================================
# ---------------- TEXT → LEADS LOGIC ------------------
# =====================================================

class TextInput(BaseModel):
    text: str


def extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    digits = re.findall(r"\+?\d[\d\s\-]{8,}\d", text)
    if not digits:
        return ""
    return re.sub(r"\D", "", digits[0])


def extract_name(text: str) -> str:
    match = re.search(r"(this is|my name is)\s+([A-Z][a-z]+)", text, re.IGNORECASE)
    return match.group(2) if match else ""


def is_business_email(email: str) -> bool:
    free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
    return email and not any(email.endswith(d) for d in free_domains)


def has_buying_intent(text: str) -> bool:
    keywords = ["price", "pricing", "quotation", "quote", "order", "buy", "requirement"]
    return any(k in text.lower() for k in keywords)


def score_lead(email: str, phone: str, message: str):
    score = 0
    reasons = []

    if email:
        score += 1
        reasons.append("valid email")

    if phone and len(phone) >= 10:
        score += 1
        reasons.append("valid phone")

    if is_business_email(email):
        score += 1
        reasons.append("business email")

    if has_buying_intent(message):
        score += 1
        reasons.append("buying intent")

    if score >= 3:
        status = "HOT"
    elif score == 2:
        status = "WARM"
    else:
        status = "COLD"

    return score, status, ", ".join(reasons)


@app.post("/text-to-leads")
def text_to_leads(data: TextInput):
    messages = [m.strip() for m in data.text.split("\n\n") if m.strip()]

    rows = []
    summary = {"total": 0, "hot": 0, "warm": 0, "cold": 0}

    for msg in messages:
        name = extract_name(msg)
        email = extract_email(msg)
        phone = extract_phone(msg)

        score, status, reason = score_lead(email, phone, msg)

        summary["total"] += 1
        summary[status.lower()] += 1

        rows.append({
            "name": name,
            "email": email,
            "phone": phone,
            "message": msg.replace("\n", " "),
            "lead_score": score,
            "lead_status": status,
            "reason": reason
        })

    output = io.StringIO()
    fieldnames = ["name", "email", "phone", "message", "lead_score", "lead_status", "reason"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=filtered_leads.csv",
            "X-Summary-Total": str(summary["total"]),
            "X-Summary-Hot": str(summary["hot"]),
            "X-Summary-Warm": str(summary["warm"]),
            "X-Summary-Cold": str(summary["cold"]),
        },
    )

# =====================================================
# ---------------- CSV CLEANING + SCORING --------------
# =====================================================

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def clean_email(email: str):
    if not email:
        return None
    email = email.strip().lower()
    return email if EMAIL_REGEX.match(email) else None


def clean_phone(phone: str):
    if not phone:
        return None
    phone = re.sub(r"[^\d]", "", phone)

    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[2:]

    return phone if len(phone) == 10 else None


def auto_detect_columns(reader):
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty")

    scores = {}

    for col in rows[0].keys():
        email_score = phone_score = name_score = 0

        for r in rows[:30]:
            val = (r.get(col) or "").strip()

            if "@" in val:
                email_score += 1

            digits = re.sub(r"[^\d]", "", val)
            if 10 <= len(digits) <= 13:
                phone_score += 1

            if val.replace(" ", "").isalpha():
                name_score += 1

        scores[col] = {
            "email": email_score,
            "phone": phone_score,
            "name": name_score
        }

    email_col = max(scores, key=lambda c: scores[c]["email"])
    phone_col = max(scores, key=lambda c: scores[c]["phone"])

    remaining = [c for c in scores if c not in [email_col, phone_col]]
    name_col = max(remaining, key=lambda c: scores[c]["name"]) if remaining else None

    return name_col, email_col, phone_col, rows


def generate_csv(data, fieldnames):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


@app.post("/clean-leads")
async def clean_leads(
    file: UploadFile = File(...),
    name_column: str = Form(None),
    email_column: str = Form(None),
    phone_column: str = Form(None),
):
    contents = await file.read()
    decoded = contents.decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(decoded)

    if name_column and email_column and phone_column:
        rows = list(reader)
        name_col, email_col, phone_col = name_column, email_column, phone_column
        detection_mode = "manual"
    else:
        name_col, email_col, phone_col, rows = auto_detect_columns(reader)
        detection_mode = "auto"

    seen_emails, seen_phones = set(), set()
    cleaned, rejected = [], []

    for row in rows:
        name = (row.get(name_col) or "").strip() if name_col else ""
        raw_email = row.get(email_col, "")
        raw_phone = row.get(phone_col, "")

        email = clean_email(raw_email)
        phone = clean_phone(raw_phone)

        if not email:
            rejected.append({
                "name": name,
                "email": raw_email,
                "phone": raw_phone,
                "reason": "Invalid email"
            })
            continue

        if not phone:
            rejected.append({
                "name": name,
                "email": raw_email,
                "phone": raw_phone,
                "reason": "Invalid phone"
            })
            continue

        if email in seen_emails or phone in seen_phones:
            rejected.append({
                "name": name,
                "email": raw_email,
                "phone": raw_phone,
                "reason": "Duplicate lead"
            })
            continue

        seen_emails.add(email)
        seen_phones.add(phone)

        score, status, reason = score_lead(email, phone, "")

        cleaned.append({
            "name": name,
            "email": email,
            "phone": phone,
            "lead_score": score,
            "lead_status": status,
            "reason": reason
        })

    cleaned_csv = generate_csv(
        cleaned,
        ["name", "email", "phone", "lead_score", "lead_status", "reason"]
    )

    rejected_csv = generate_csv(
        rejected,
        ["name", "email", "phone", "reason"]
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("cleaned.csv", cleaned_csv)
        zipf.writestr("rejected.csv", rejected_csv)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=lead_results.zip",
            "X-Detection-Mode": detection_mode,
            "X-Total": str(len(cleaned) + len(rejected)),
            "X-Valid": str(len(cleaned)),
            "X-Rejected": str(len(rejected)),
        }
    )
