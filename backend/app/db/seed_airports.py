"""
Populates the airports table with data from OpenFlights (airports.dat).

Geographic scope: Europe + North Africa (Morocco, Tunisia, Egypt).
Filtering is driven by COUNTRY_CONTINENT: only mapped countries are
inserted into the DB. Adding a country to that dict is enough to extend
coverage — no other code changes are needed.

CMD: docker compose exec backend python -m app.db.seed_airports
"""


import asyncio
import csv
import io

import httpx
from sqlalchemy.dialects.postgresql import insert

from app.db.database import async_session_maker
from app.models.airport import Airport

AIRPORTS_URL = (
    "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat"
)

# Maps country name → ISO continent code (EU, AF, AS, NA, SA, OC).
# Only countries listed here will be loaded into the DB.
COUNTRY_CONTINENT: dict[str, str] = {
    # Europe
    "Albania": "EU", "Andorra": "EU", "Austria": "EU", "Belarus": "EU",
    "Belgium": "EU", "Bosnia and Herzegovina": "EU", "Bulgaria": "EU",
    "Croatia": "EU", "Cyprus": "EU", "Czech Republic": "EU", "Denmark": "EU",
    "Estonia": "EU", "Finland": "EU", "France": "EU", "Germany": "EU",
    "Greece": "EU", "Hungary": "EU", "Iceland": "EU", "Ireland": "EU",
    "Italy": "EU", "Kosovo": "EU", "Latvia": "EU", "Liechtenstein": "EU",
    "Lithuania": "EU", "Luxembourg": "EU", "Malta": "EU", "Moldova": "EU",
    "Monaco": "EU", "Montenegro": "EU", "Netherlands": "EU",
    "North Macedonia": "EU", "Norway": "EU", "Poland": "EU", "Portugal": "EU",
    "Romania": "EU", "Russia": "EU", "San Marino": "EU", "Serbia": "EU",
    "Slovakia": "EU", "Slovenia": "EU", "Spain": "EU", "Sweden": "EU",
    "Switzerland": "EU", "Turkey": "EU", "Ukraine": "EU",
    "United Kingdom": "EU", "Vatican City": "EU",
    # North Africa — common low-cost destinations from Europe
    "Morocco": "AF", "Tunisia": "AF", "Egypt": "AF",
}

# Set of all countries included in the seed (keys of the mapping above)
EUROPEAN_COUNTRIES = set(COUNTRY_CONTINENT.keys())


async def seed() -> None:
    print("Downloading airports.dat from OpenFlights...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(AIRPORTS_URL)
        resp.raise_for_status()

    rows: list[dict] = []
    reader = csv.reader(io.StringIO(resp.text))
    for row in reader:
        if len(row) < 8:
            continue

        iata = row[4].strip('"')
        # Skip airports with a non valid IATA code
        if not iata or iata == r"\N" or len(iata) != 3:
            continue

        country = row[3].strip('"')
        if country not in EUROPEAN_COUNTRIES:
            continue

        try:
            lat = float(row[6])
            lon = float(row[7])
        except ValueError:
            continue

        rows.append(
            {
                "iata_code": iata,
                "name": row[1].strip('"'),
                "city": row[2].strip('"'),
                "country": country,
                "continent": COUNTRY_CONTINENT.get(country),
                "latitude": lat,
                "longitude": lon,
                "is_active": True,
            }
        )

    if not rows:
        print("WARNING: no airports found. Check the CSV source.")
        return

    print(f"Found {len(rows)} airports. Inserting into DB...")

    async with async_session_maker() as session:
        stmt = insert(Airport).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["iata_code"],
            set_={"continent": stmt.excluded.continent},
        )
        await session.execute(stmt)
        await session.commit()

    print(f"Seed complete: {len(rows)} airports inserted/updated.")


if __name__ == "__main__":
    asyncio.run(seed())
