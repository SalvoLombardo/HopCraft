"""
Test funzioni geo: haversine_km, estimate_radius_km, estimate_stops.
Tutte le funzioni sono pure (no I/O) — nessun mock necessario.
"""
import pytest

from app.utils.geo import estimate_radius_km, estimate_stops, haversine_km


# ---------------------------------------------------------------------------
# haversine_km
# ---------------------------------------------------------------------------

class TestHaversineKm:

    def test_same_point_returns_zero(self):
        assert haversine_km(37.47, 15.06, 37.47, 15.06) == pytest.approx(0.0, abs=0.1)

    def test_rome_to_milan(self):
        # Roma FCO (41.80, 12.24) → Milano MXP (45.63, 8.72) ≈ 511 km
        dist = haversine_km(41.80, 12.24, 45.63, 8.72)
        assert 490 < dist < 530

    def test_symmetry(self):
        d1 = haversine_km(37.47, 15.06, 41.80, 12.24)
        d2 = haversine_km(41.80, 12.24, 37.47, 15.06)
        assert d1 == pytest.approx(d2, abs=0.01)

    def test_catania_to_athens(self):
        # CTA (37.47, 15.06) → ATH (37.94, 23.94) ≈ 800 km
        dist = haversine_km(37.47, 15.06, 37.94, 23.94)
        assert 750 < dist < 850

    def test_result_is_positive(self):
        assert haversine_km(51.5, -0.1, 48.9, 2.3) > 0


# ---------------------------------------------------------------------------
# estimate_radius_km
# ---------------------------------------------------------------------------

class TestEstimateRadiusKm:

    # --- Fascia 1: ≤ 7 giorni (200 km/giorno) ---

    def test_1_day(self):
        assert estimate_radius_km(1) == 200

    def test_5_days(self):
        assert estimate_radius_km(5) == 1000

    def test_7_days(self):
        assert estimate_radius_km(7) == 1400

    # --- Fascia 2: 8-15 giorni (1400 + 150 km/giorno) ---

    def test_8_days(self):
        assert estimate_radius_km(8) == 1400 + 150  # 1550

    def test_15_days(self):
        assert estimate_radius_km(15) == 1400 + 8 * 150  # 2600

    # --- Fascia 3: > 15 giorni (2600 + 100 km/giorno) ---

    def test_16_days(self):
        assert estimate_radius_km(16) == 2600 + 100  # 2700

    def test_25_days(self):
        assert estimate_radius_km(25) == 2600 + 10 * 100  # 3600

    # --- Cap a 5000 km ---

    def test_cap_at_5000(self):
        assert estimate_radius_km(50) == 5000

    def test_large_value_capped(self):
        assert estimate_radius_km(100) == 5000

    # --- Continuità alle transizioni ---

    def test_continuity_7_to_8(self):
        """Non ci deve essere un salto di più di 200 km tra giorno 7 e 8."""
        diff = estimate_radius_km(8) - estimate_radius_km(7)
        assert 0 < diff <= 200

    def test_continuity_15_to_16(self):
        diff = estimate_radius_km(16) - estimate_radius_km(15)
        assert 0 < diff <= 200


# ---------------------------------------------------------------------------
# estimate_stops
# ---------------------------------------------------------------------------

class TestEstimateStops:

    # --- Fascia 1: ≤ 7 giorni, max 2 tappe ---

    def test_5_days_gives_1_stop(self):
        assert estimate_stops(5) == 1

    def test_6_days_gives_2_stops(self):
        assert estimate_stops(6) == 2

    def test_7_days_gives_2_stops(self):
        assert estimate_stops(7) == 2

    # --- Fascia 2: 8-15 giorni, max 3 tappe ---

    def test_8_days_gives_2_stops(self):
        assert estimate_stops(8) == 2

    def test_12_days_gives_3_stops(self):
        assert estimate_stops(12) == 3

    def test_15_days_gives_3_stops(self):
        assert estimate_stops(15) == 3

    # --- Fascia 3: > 15 giorni, max 4 tappe ---

    def test_16_days_gives_3_stops(self):
        assert estimate_stops(16) == 3

    def test_20_days_gives_4_stops(self):
        assert estimate_stops(20) == 4

    def test_25_days_gives_4_stops(self):
        assert estimate_stops(25) == 4

    # --- Continuità alle transizioni ---

    def test_continuity_7_to_8(self):
        assert estimate_stops(8) >= estimate_stops(7)

    def test_continuity_15_to_16(self):
        assert estimate_stops(16) >= estimate_stops(15) - 1

    # --- Limiti massimi rispettati ---

    def test_max_stops_short_trip(self):
        assert estimate_stops(7) <= 2

    def test_max_stops_medium_trip(self):
        assert estimate_stops(15) <= 3

    def test_max_stops_long_trip(self):
        assert estimate_stops(25) <= 4
