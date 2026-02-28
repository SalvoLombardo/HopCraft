"""
Fixture condivise per la test suite HopCraft.

Tutte le dipendenze esterne (DB, HTTP, Redis) vengono simulate con
unittest.mock — nessun servizio reale è necessario per eseguire i test.
"""
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.providers.base import FlightOffer


# ---------------------------------------------------------------------------
# Aeroporti fittizi
# ---------------------------------------------------------------------------

def _make_airport(iata: str, city: str, lat: float, lon: float, country: str = "Italy") -> MagicMock:
    a = MagicMock()
    a.iata_code = iata
    a.city = city
    a.country = country
    a.continent = "EU"
    a.latitude = lat
    a.longitude = lon
    a.is_active = True
    return a


@pytest.fixture
def airport_cta():
    """Catania Fontanarossa — aeroporto di partenza di riferimento."""
    return _make_airport("CTA", "Catania", 37.47, 15.06)


@pytest.fixture
def airport_fco():
    """Roma Fiumicino."""
    return _make_airport("FCO", "Rome", 41.80, 12.24)


@pytest.fixture
def airport_ath():
    """Atene."""
    return _make_airport("ATH", "Athens", 37.94, 23.94, "Greece")


@pytest.fixture
def airport_bud():
    """Budapest."""
    return _make_airport("BUD", "Budapest", 47.44, 19.26, "Hungary")


@pytest.fixture
def sample_airports(airport_cta, airport_fco, airport_ath, airport_bud):
    """Lista di 4 aeroporti di test."""
    return [airport_cta, airport_fco, airport_ath, airport_bud]


# ---------------------------------------------------------------------------
# FlightOffer fittizi
# ---------------------------------------------------------------------------

@pytest.fixture
def offer_fco_cta():
    """Volo Roma→Catania economico."""
    return FlightOffer(
        origin="FCO",
        destination="CTA",
        departure="2026-06-01T08:00:00",
        price_eur=49.99,
        airline="ITA",
        direct=True,
        duration_minutes=90,
    )


@pytest.fixture
def offer_ath_cta():
    """Volo Atene→Catania più caro."""
    return FlightOffer(
        origin="ATH",
        destination="CTA",
        departure="2026-06-01T10:30:00",
        price_eur=89.00,
        airline="Aegean",
        direct=True,
        duration_minutes=120,
    )


# ---------------------------------------------------------------------------
# AsyncSession mock
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """AsyncSession SQLAlchemy completamente mockato."""
    return AsyncMock()


def make_session_returning(airports=None, cache_entries=None):
    """
    Factory che costruisce un AsyncSession mock che restituisce i dati passati.

    La prima chiamata a session.execute() restituisce gli aeroporti,
    la seconda le entries di cache.
    """
    session = AsyncMock()
    airport_result = MagicMock()
    airport_result.scalars.return_value.all.return_value = airports or []

    cache_result = MagicMock()
    cache_result.scalars.return_value = iter(cache_entries or [])

    # execute() restituisce alternativamente airports e cache
    session.execute.side_effect = [airport_result, cache_result]
    return session


# ---------------------------------------------------------------------------
# Data di riferimento
# ---------------------------------------------------------------------------

@pytest.fixture
def date_from():
    return date(2026, 6, 1)


@pytest.fixture
def date_to():
    return date(2026, 6, 7)


@pytest.fixture
def now_utc():
    return datetime.now(timezone.utc)
