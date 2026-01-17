# Lead Cleaning API

Upload a CSV file containing leads and get a cleaned version.

### CSV Format
name,email,phone

### Features
- Validates phone numbers (10 digits)
- Validates email format
- Removes invalid leads
- Returns cleaned CSV

### Endpoint
POST /clean-leads
