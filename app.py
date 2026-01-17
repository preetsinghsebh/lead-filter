from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
import csv
import io
import re
import zipfile

app = FastAPI(title="Lead Filter API", version="3.0")

# ------------------------
# Validation Helpers
# ------------------------

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def clean_email(email: str):
    if not email:
        return None
    email = email.strip().lower()
    if not EMAIL_REGEX.match(email):
        return None
    return email


def clean_phone(phone: str):
    if not phone:
        return None
    # remove spaces, +, -, brackets etc.
    phone = re.sub(r"[^\d]", "", phone)

    # India support (91XXXXXXXXXX → XXXXXXXXXX)
    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[2:]

    if len(phone) == 10:
        return phone
    return None


# ------------------------
# Auto Column Detection
# ------------------------

def auto_detect_columns(reader):
    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty")

    scores = {}

    for col in rows[0].keys():
        email_score = 0
        phone_score = 0
        name_score = 0

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


# ------------------------
# CSV Generator
# ------------------------

def generate_csv(data, fieldnames):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(data)
    output.seek(0)
    return output.getvalue()


# ------------------------
# Main Endpoint
# ------------------------

@app.post("/clean-leads")
async def clean_leads(file: UploadFile = File(...)):
    contents = await file.read()
    decoded = contents.decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(decoded)

    name_col, email_col, phone_col, rows = auto_detect_columns(reader)

    seen_emails = set()
    seen_phones = set()

    cleaned = []
    rejected = []

    for row in rows:
        name = (row.get(name_col) or "").strip() if name_col else ""
        raw_email = row.get(email_col, "")
        raw_phone = row.get(phone_col, "")

        email = clean_email(raw_email)
        phone = clean_phone(raw_phone)

        reason = None

        if not email:
            reason = "Invalid email format"
        elif not phone:
            reason = "Invalid phone number"
        elif email in seen_emails:
            reason = "Duplicate email"
        elif phone in seen_phones:
            reason = "Duplicate phone"

        if reason:
            rejected.append({
                "name": name,
                "email": raw_email,
                "phone": raw_phone,
                "reason": reason
            })
        else:
            seen_emails.add(email)
            seen_phones.add(phone)
            cleaned.append({
                "name": name,
                "email": email,
                "phone": phone
            })

    # Generate CSVs
    cleaned_csv = generate_csv(cleaned, ["name", "email", "phone"])
    rejected_csv = generate_csv(rejected, ["name", "email", "phone", "reason"])

    # ------------------------
    # ZIP FILE CREATION
    # ------------------------
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("cleaned.csv", cleaned_csv)
        zipf.writestr("rejected.csv", rejected_csv)

    zip_buffer.seek(0)

    # ------------------------
    # STATS (for headers/debug)
    # ------------------------
    total = len(cleaned) + len(rejected)
    valid = len(cleaned)
    invalid = len([r for r in rejected if "Invalid" in r["reason"]])
    duplicates = len([r for r in rejected if "Duplicate" in r["reason"]])

    # ------------------------
    # ZIP DOWNLOAD RESPONSE
    # ------------------------
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=lead_results.zip",
            "X-Total": str(total),
            "X-Valid": str(valid),
            "X-Invalid": str(invalid),
            "X-Duplicates": str(duplicates),
            "X-Detected-Name-Column": str(name_col),
            "X-Detected-Email-Column": str(email_col),
            "X-Detected-Phone-Column": str(phone_col),
        }
    )
