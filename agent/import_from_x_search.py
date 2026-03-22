import os
import sys
import json
import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

print("=== Grok X Search Importer started ===")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set!")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# Read JSON from file argument or stdin
if len(sys.argv) > 1:
    json_path = sys.argv[1]
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
else:
    data = json.load(sys.stdin)

if not isinstance(data, list):
    data = [data]

session = Session()
inserted = 0

try:
    print(f"Received {len(data)} projects from Grok X search")

    for item in data:
        name = item.get("name", "")[:255]
        link = item.get("link", "")[:255]
        snippet = item.get("snippet", "")
        source = "Grok X Search"

        # Deduplicate
        exists = session.execute(
            text("SELECT 1 FROM projects WHERE link = :link OR name = :name"),
            {"link": link, "name": name}
        ).scalar()

        if exists:
            print(f"Skipped duplicate: {name}")
            continue

        # Basic extraction (budget, location, sector)
        text = name + " " + snippet
        budget_match = re.search(r'(\$[\d.,]+ ?(million|billion))', text, re.I)
        budget = float(re.sub(r'[^\d.]', '', budget_match.group(1))) * (1e6 if "million" in (budget_match.group(1) or "").lower() else 1e9) if budget_match else None

        location_match = re.search(r'(Dubai|UAE|Saudi|Indiana|Louisiana|Pennsylvania|Texas|Utah|Wyoming|Georgetown|Wichita|Lebanon|Egypt|Moon|Lunar)', text, re.I)
        location = location_match.group(1) if location_match else "Unknown"

        sector = "Unknown"
        lower = text.lower()
        if any(w in lower for w in ["hotel", "hospitality"]):
            sector = "Hospitality"
        elif any(w in lower for w in ["data center", "ai", "gigawatt"]):
            sector = "Data Centers"
        elif any(w in lower for w in ["airport", "high-rise", "tower"]):
            sector = "Infrastructure / High-Rise"
        elif any(w in lower for w in ["lunar", "moon"]):
            sector = "Space / Lunar"

        session.execute(
            text("""
                INSERT INTO projects (
                    name, status, last_updated, announcement_date, link,
                    budget_usd, country, industry_sector
                ) VALUES (
                    :name, 'Pending Review', CURRENT_DATE, CURRENT_DATE, :link,
                    :budget, :country, :sector
                )
            """),
            {
                "name": name,
                "link": link,
                "budget": budget,
                "country": location,
                "sector": sector
            }
        )
        inserted += 1
        print(f"Inserted: {name}")

    session.commit()
    print(f"Successfully imported {inserted} new projects from Grok X search.")

except Exception as e:
    print(f"Error: {str(e)}")
    session.rollback()
finally:
    session.close()
