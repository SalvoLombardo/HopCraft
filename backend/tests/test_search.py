"""
Test per il modulo search_engine: _build_result (puro) e reverse_search (mock).

Tutte le dipendenze esterne vengono sostituite con mock:
  - AsyncSession        → side_effect che alterna risposta airports / cache
  - get_providers_in_order → lista con un provider fittizio
  - get_provider_quotas    → saldi fissi
  - check_rate_limit    → restituisce True per default (limite non raggiunto)
  - save_to_cache       → AsyncMock silenzioso
"""
from dataclasses import asdict
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.providers.base import FlightOffer
from app.services.search_engine import _build_result, reverse_search

# Quota fittizia restituita da get_provider_quotas nei test
_FAKE_QUOTAS = {"serpapi": 200, "amadeus": 1800}


# ---------------------------------------------------------------------------
# Helpers per costruire mock di sessione
# ---------------------------------------------------------------------------

def _make_airport(iata, city, lat, lon):
    a = MagicMock()
    a.iata_code = iata
    a.city = city
    a.latitude = lat
    a.longitude = lon
    a.is_active = True
    return a


def _make_cache_entry(origin, destination, departure_date, offers, fetched_at=None):
    """Crea un oggetto FlightCache fittizio con raw_response popolato."""
    entry = MagicMock()
    entry.origin = origin
    entry.destination = destination
    entry.departure_date = departure_date
    entry.fetched_at = fetched_at or datetime(2026, 6, 1, 6, 0, 0)
    entry.raw_response = [asdict(o) for o in offers]
    return entry


def _build_session(airports, cache_entries):
    """
    Costruisce un AsyncSession mock che:
    - prima chiamata execute() → restituisce gli airports
    - seconda chiamata execute() → restituisce le cache entries
    """
    session = AsyncMock()

    airport_result = MagicMock()
    airport_result.scalars.return_value.all.return_value = airports

    cache_result = MagicMock()
    cache_result.scalars.return_value = iter(cache_entries)

    session.execute.side_effect = [airport_result, cache_result]
    return session


# ---------------------------------------------------------------------------
# Test _build_result — funzione pura
# ---------------------------------------------------------------------------

class TestBuildResult:

    def test_fields_copied_correctly(self):
        offer = FlightOffer(
            origin="FCO", destination="CTA",
            departure="2026-06-01T08:00:00",
            price_eur=49.99, airline="ITA",
            direct=True, duration_minutes=90,
        )
        airport = _make_airport("FCO", "Rome", 41.80, 12.24)
        fetched_at = datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        result = _build_result(offer, airport, fetched_at)

        assert result["origin"] == "FCO"
        assert result["origin_city"] == "Rome"
        assert result["price_eur"] == 49.99
        assert result["airline"] == "ITA"
        assert result["departure"] == "2026-06-01T08:00:00"
        assert result["direct"] is True
        assert result["duration_minutes"] == 90
        assert result["latitude"] == pytest.approx(41.80)
        assert result["longitude"] == pytest.approx(12.24)

    def test_internal_fetched_at_included(self):
        offer = FlightOffer("FCO", "CTA", "2026-06-01T08:00:00", 49.99, "ITA", True, 90)
        airport = _make_airport("FCO", "Rome", 41.80, 12.24)
        ts = datetime(2026, 6, 1, 12, 0, 0)

        result = _build_result(offer, airport, ts)

        assert "_fetched_at" in result
        assert result["_fetched_at"] == ts


# ---------------------------------------------------------------------------
# Test reverse_search — DB + provider mockati
# ---------------------------------------------------------------------------

DESTINATION = "CTA"
DATE_FROM = date(2026, 6, 1)
DATE_TO = date(2026, 6, 3)


class TestReverseSearch:

    async def test_all_from_cache(self):
        """Se tutti gli aeroporti hanno cache valida, il provider non viene chiamato."""
        fco_airport = _make_airport("FCO", "Rome", 41.80, 12.24)
        offer = FlightOffer("FCO", "CTA", "2026-06-01T08:00:00", 49.99, "ITA", True, 90)
        cache_entry = _make_cache_entry("FCO", "CTA", DATE_FROM, [offer])

        session = _build_session([fco_airport], [cache_entry])
        mock_provider = AsyncMock()

        with patch("app.services.search_engine.get_providers_in_order",
                   new=AsyncMock(return_value=[("serpapi", mock_provider)])), \
             patch("app.services.search_engine.get_provider_quotas",
                   new=AsyncMock(return_value=_FAKE_QUOTAS)), \
             patch("app.services.search_engine.check_rate_limit", new=AsyncMock(return_value=True)), \
             patch("app.services.search_engine.save_to_cache", new=AsyncMock()):

            results, all_from_cache, _, status = await reverse_search(
                session=session,
                destination=DESTINATION,
                date_from=DATE_FROM,
                date_to=DATE_TO,
            )

        assert all_from_cache is True
        assert len(results) == 1
        assert results[0]["origin"] == "FCO"
        assert status is not None
        assert status.serpapi_remaining == 200
        mock_provider.search_one_way.assert_not_called()

    async def test_no_cache_provider_returns_offers(self):
        """Cache vuota → il provider viene chiamato e i risultati vengono restituiti."""
        fco_airport = _make_airport("FCO", "Rome", 41.80, 12.24)
        offer = FlightOffer("FCO", "CTA", "2026-06-01T08:00:00", 35.00, "Ryanair", True, 90)

        session = _build_session([fco_airport], [])

        mock_provider = AsyncMock()
        mock_provider.search_one_way = AsyncMock(return_value=[offer])

        with patch("app.services.search_engine.get_providers_in_order",
                   new=AsyncMock(return_value=[("serpapi", mock_provider)])), \
             patch("app.services.search_engine.get_provider_quotas",
                   new=AsyncMock(return_value=_FAKE_QUOTAS)), \
             patch("app.services.search_engine.check_rate_limit", new=AsyncMock(return_value=True)), \
             patch("app.services.search_engine.save_to_cache", new=AsyncMock()):

            results, all_from_cache, _, _ = await reverse_search(
                session=session,
                destination=DESTINATION,
                date_from=DATE_FROM,
                date_to=DATE_TO,
            )

        assert all_from_cache is False
        assert len(results) == 1
        assert results[0]["price_eur"] == 35.00

    async def test_rate_limit_exhausted_returns_empty(self):
        """Se il rate limit è esaurito per tutti i provider, nessuna chiamata → lista vuota."""
        fco_airport = _make_airport("FCO", "Rome", 41.80, 12.24)

        session = _build_session([fco_airport], [])
        mock_provider = AsyncMock()

        with patch("app.services.search_engine.get_providers_in_order",
                   new=AsyncMock(return_value=[("serpapi", mock_provider)])), \
             patch("app.services.search_engine.get_provider_quotas",
                   new=AsyncMock(return_value=_FAKE_QUOTAS)), \
             patch("app.services.search_engine.check_rate_limit", new=AsyncMock(return_value=False)), \
             patch("app.services.search_engine.save_to_cache", new=AsyncMock()):

            results, all_from_cache, _, _ = await reverse_search(
                session=session,
                destination=DESTINATION,
                date_from=DATE_FROM,
                date_to=DATE_TO,
            )

        assert results == []
        mock_provider.search_one_way.assert_not_called()

    async def test_provider_failure_logs_and_continues(self, caplog):
        """Se il provider fallisce su un'origine, viene loggato e si continua."""
        import logging

        fco_airport = _make_airport("FCO", "Rome", 41.80, 12.24)
        ath_airport = _make_airport("ATH", "Athens", 37.94, 23.94)
        # ATH ha un'offerta in cache; FCO farà fallire il provider
        offer_ath = FlightOffer("ATH", "CTA", "2026-06-01T09:00:00", 79.00, "Aegean", True, 120)
        cache_entry_ath = _make_cache_entry("ATH", "CTA", DATE_FROM, [offer_ath])

        session = _build_session([fco_airport, ath_airport], [cache_entry_ath])

        mock_provider = AsyncMock()
        mock_provider.search_one_way = AsyncMock(side_effect=Exception("Connection error"))

        with patch("app.services.search_engine.get_providers_in_order",
                   new=AsyncMock(return_value=[("serpapi", mock_provider)])), \
             patch("app.services.search_engine.get_provider_quotas",
                   new=AsyncMock(return_value=_FAKE_QUOTAS)), \
             patch("app.services.search_engine.check_rate_limit", new=AsyncMock(return_value=True)), \
             patch("app.services.search_engine.save_to_cache", new=AsyncMock()), \
             caplog.at_level(logging.WARNING, logger="app.services.search_engine"):

            results, _, _, _ = await reverse_search(
                session=session,
                destination=DESTINATION,
                date_from=DATE_FROM,
                date_to=DATE_TO,
            )

        # ATH è in cache → risultato presente; FCO ha fallito → assente
        origins = [r["origin"] for r in results]
        assert "ATH" in origins
        assert "FCO" not in origins
        assert any("FCO" in msg for msg in caplog.messages)

    async def test_results_sorted_by_price(self):
        """La lista finale deve essere ordinata per prezzo crescente."""
        airports = [
            _make_airport("FCO", "Rome", 41.80, 12.24),
            _make_airport("ATH", "Athens", 37.94, 23.94),
            _make_airport("BUD", "Budapest", 47.44, 19.26),
        ]
        offers = [
            FlightOffer("FCO", "CTA", "2026-06-01T08:00:00", 99.00, "ITA", True, 90),
            FlightOffer("ATH", "CTA", "2026-06-01T09:00:00", 45.00, "Aegean", True, 120),
            FlightOffer("BUD", "CTA", "2026-06-01T10:00:00", 65.00, "Wizz", True, 110),
        ]
        cache_entries = [
            _make_cache_entry(o.origin, "CTA", DATE_FROM, [o]) for o in offers
        ]

        session = _build_session(airports, cache_entries)

        with patch("app.services.search_engine.get_providers_in_order",
                   new=AsyncMock(return_value=[])), \
             patch("app.services.search_engine.get_provider_quotas",
                   new=AsyncMock(return_value=_FAKE_QUOTAS)), \
             patch("app.services.search_engine.check_rate_limit", new=AsyncMock(return_value=True)), \
             patch("app.services.search_engine.save_to_cache", new=AsyncMock()):

            results, _, _, _ = await reverse_search(
                session=session,
                destination=DESTINATION,
                date_from=DATE_FROM,
                date_to=DATE_TO,
            )

        prices = [r["price_eur"] for r in results]
        assert prices == sorted(prices)

    async def test_geographic_filter_limits_airports(self):
        """Con filtro raggio, solo gli aeroporti entro il raggio vengono interrogati."""
        fco_airport = _make_airport("FCO", "Rome", 41.80, 12.24)
        ber_airport = _make_airport("BER", "Berlin", 52.37, 13.50)

        session = _build_session([fco_airport, ber_airport], [])

        captured_origins = []

        async def fake_search_one_way(origin, destination, *args, **kwargs):
            captured_origins.append(origin)
            return []

        mock_provider = AsyncMock()
        mock_provider.search_one_way = fake_search_one_way

        with patch("app.services.search_engine.get_providers_in_order",
                   new=AsyncMock(return_value=[("serpapi", mock_provider)])), \
             patch("app.services.search_engine.get_provider_quotas",
                   new=AsyncMock(return_value=_FAKE_QUOTAS)), \
             patch("app.services.search_engine.check_rate_limit", new=AsyncMock(return_value=True)), \
             patch("app.services.search_engine.save_to_cache", new=AsyncMock()):

            await reverse_search(
                session=session,
                destination=DESTINATION,
                date_from=DATE_FROM,
                date_to=DATE_TO,
                origin_lat=37.47,
                origin_lon=15.06,
                radius_km=1000,
            )

        # Solo FCO (~900km da CTA) dovrebbe essere interrogato
        assert "FCO" in captured_origins
        assert "BER" not in captured_origins
