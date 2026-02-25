"""
This will populate the table airports with eu airports frm OpenFlight

CMD=docker compose exec backend python -m app.db.seed_airports
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

# Mapping paese → codice continente ISO (EU, AF, AS, NA, SA, OC)
# Copre tutti i paesi presenti nel seed attuale.
COUNTRY_CONTINENT: dict[str, str] = {
    # Europa
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
    # Nord Africa — destinazioni comuni low-cost europee
    "Morocco": "AF", "Tunisia": "AF", "Egypt": "AF",
}

# Paesi inclusi nel seed (chiavi del mapping sopra)
EUROPEAN_COUNTRIES = set(COUNTRY_CONTINENT.keys())


async def seed() -> None:
    print("Download airports.dat da OpenFlights...")
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
        print("ATTENZIONE: nessun aeroporto trovato. Controllare il CSV.")
        return

    print(f"Trovati {len(rows)} aeroporti europei. Inserimento nel DB...")

    async with async_session_maker() as session:
        stmt = (
            insert(Airport)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["iata_code"])
        )
        await session.execute(stmt)
        await session.commit()

    print(f"Seed completato: {len(rows)} aeroporti inseriti (duplicati ignorati).")


if __name__ == "__main__":
    asyncio.run(seed())
