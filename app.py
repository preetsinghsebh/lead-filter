from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
import csv
import io

app = FastAPI()

@app.post("/clean-leads")
async def filter_leads_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        return {"error": "Only CSV files allowed"}

    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    required_fields = {"name", "email", "phone"}
    if not required_fields.issubset(reader.fieldnames):
        return {"error": "CSV must contain name, email, phone columns"}

    filtered = []
    for row in reader:
        phone = row.get("phone", "").strip()
        email = row.get("email", "").strip()

        if phone.isdigit() and len(phone) == 10 and "@" in email:
            row["phone"] = str(phone)  # force phone as string
            filtered.append(row)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(filtered)

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=filtered_leads.csv"}
    )

@app.post("/clean-leads-stats")
async def clean_leads_stats(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        return {"error": "Only CSV files allowed"}

    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)

    required_fields = {"name", "email", "phone"}
    if not required_fields.issubset(reader.fieldnames):
        return {"error": "CSV must contain name, email, phone columns"}

    rows = list(reader)
    total_rows = len(rows)

    valid = 0
    for row in rows:
        phone = row.get("phone", "").strip()
        email = row.get("email", "").strip()

        if phone.isdigit() and len(phone) == 10 and "@" in email:
            valid += 1

    return {
        "total": total_rows,
        "valid": valid,
        "removed": total_rows - valid
    }
