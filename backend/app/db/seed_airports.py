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

# Paesi europei + Nord Africa (Tunisia, Marocco, Egitto) per coprire destinazioni
# raggiungibili con low-cost europee
EUROPEAN_COUNTRIES = {
    "Albania", "Andorra", "Austria", "Belarus", "Belgium",
    "Bosnia and Herzegovina", "Bulgaria", "Croatia", "Cyprus",
    "Czech Republic", "Denmark", "Estonia", "Finland", "France",
    "Germany", "Greece", "Hungary", "Iceland", "Ireland", "Italy",
    "Kosovo", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg",
    "Malta", "Moldova", "Monaco", "Montenegro", "Netherlands",
    "North Macedonia", "Norway", "Poland", "Portugal", "Romania",
    "Russia", "San Marino", "Serbia", "Slovakia", "Slovenia",
    "Spain", "Sweden", "Switzerland", "Turkey", "Ukraine",
    "United Kingdom", "Vatican City",
    # Nord Africa — destinazioni comuni low-cost
    "Morocco", "Tunisia", "Egypt",
}


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
