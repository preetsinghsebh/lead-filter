from fastapi import FastAPI
from typing import List

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Lead Filter API running"}

@app.post("/filter-leads")
def filter_leads(leads: List[dict]):
    filtered = []
    for lead in leads:
        if lead.get("email") and lead.get("phone") and len(lead.get("phone")) >= 10:
            filtered.append(lead)

    return {
        "total_received": len(leads),
        "total_filtered": len(filtered),
        "filtered_leads": filtered
    }
