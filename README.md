# Lead Cleaner API 🚀

A FastAPI-based API to clean and validate lead CSV files.

## Features
- Validates phone numbers (10 digits)
- Validates email format
- Removes invalid rows
- Preserves phone numbers as strings
- Returns cleaned CSV
- Returns stats in JSON

## Endpoints

### Clean CSV
POST `/clean-leads`

Returns cleaned CSV file.

### Stats
POST `/clean-leads-stats`

Returns:
```json
{
  "total": 100,
  "valid": 75,
  "removed": 25
}
