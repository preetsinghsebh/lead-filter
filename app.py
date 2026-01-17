from fastapi import FastAPI, UploadFile, File, Form
import csv
import io

app = FastAPI()

@app.post("/clean-leads")
async def clean_leads(
    file: UploadFile = File(...),
    name_column: str = Form(...),
    email_column: str = Form(...),
    phone_column: str = Form(...)
):
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    filtered = []
    total = 0
    valid = 0

    for row in reader:
        total += 1
        name = row.get(name_column, "").strip()
        email = row.get(email_column, "").strip()
        phone = row.get(phone_column, "").strip()

        if phone.isdigit() and len(phone) == 10 and "@" in email:
            filtered.append({
                "name": name,
                "email": email,
                "phone": phone
            })
            valid += 1

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "email", "phone"])
    writer.writeheader()
    writer.writerows(filtered)
    output.seek(0)

    return {
        "total": total,
        "valid": valid,
        "removed": total - valid,
        "cleaned_data": output.getvalue()
    }
