from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
import csv
import io

app = FastAPI()

@app.post("/filter-leads-csv")
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
        phone = row.get("phone", "")
        email = row.get("email", "")
        if phone.isdigit() and len(phone) == 10 and "@" in email:
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
