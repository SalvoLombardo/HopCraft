"""
LLM Provider Layer — abstract base classes and shared utilities.

The prompt is defined once here so that every provider receives
the exact same input.
"""
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SuggestedItinerary:
    route: list[str]           # e.g. ["CTA", "ATH", "SOF", "BUD", "CTA"]
    reasoning: str
    estimated_difficulty: str  # "easy" | "medium" | "hard"
    best_season: list[str]     # e.g. ["apr", "may", "jun"]


class LLMProvider(ABC):
    # Abstract method enforces a consistent interface across all providers
    @abstractmethod
    async def generate_itineraries(
        self,
        origin: str,
        duration_days: int,
        budget_per_leg: float,
        season: str,
        num_stops: int,
        available_airports: list[str],
        provider_hint: str = "",
    ) -> list[SuggestedItinerary]:
        """
        Generate candidate multi-city itineraries.

        Args:
            origin:              IATA code of the departure/return airport
            duration_days:       total trip duration in days
            budget_per_leg:      max budget per leg per person in EUR
            season:              travel season (e.g. "summer 2026")
            num_stops:           number of intermediate stops to suggest
            available_airports:  list of "IATA (City)" strings within the search radius
        """
        ...


# ---------------------------------------------------------------------------
# Shared prompt — identical for all providers
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert in European travel and low-cost flight routes.
Given a departure point, a trip duration, a per-leg budget, and a list
of reachable airports, generate 8-10 optimised multi-city itineraries.

Reply ONLY in JSON, with no preamble or markdown.
Format:
[
  {
    "route": ["CTA", "ATH", "SOF", "BUD", "CTA"],
    "reasoning": "Balkan route with excellent low-cost connections",
    "estimated_difficulty": "easy",
    "best_season": ["apr", "may", "jun", "sep", "oct"]
  }
]

Criteria:
- Favour routes with well-known low-cost connections (Ryanair, Wizz Air, easyJet)
- Each stop must make geographic sense (no zig-zagging)
- Take seasonality into account
- Stay within the indicated per-leg budget
- The last flight must return to the origin"""


def build_user_prompt(
    origin: str,
    duration_days: int,
    budget_per_leg: float,
    season: str,
    num_stops: int,
    available_airports: list[str],
    provider_hint: str = "",
) -> str:
    airport_list = ", ".join(available_airports)
    prompt = (
        f"Origin: {origin}\n"
        f"Trip duration: {duration_days} days\n"
        f"Budget per leg per person: {budget_per_leg}€\n"
        f"Season: {season}\n"
        f"Number of intermediate stops: {num_stops}\n"
        f"Available airports within radius: {airport_list}"
    )
    if provider_hint:
        prompt += f"\nProvider constraint: {provider_hint}"
    return prompt


def parse_itineraries(raw: str) -> list[SuggestedItinerary]:
    """
    Parses the raw model response into a list of SuggestedItinerary objects.

    Handles cases where the model wraps JSON in markdown code blocks
    despite instructions (common behaviour on some providers).
    """
    # Strip optional ```json ... ``` or ``` ... ``` wrappers
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    cleaned = match.group(1).strip() if match else raw.strip()

    try:
        data = json.loads(cleaned)
        result: list[SuggestedItinerary] = []
        for item in data:
            result.append(
                SuggestedItinerary(
                    route=item["route"],
                    reasoning=item.get("reasoning", ""),
                    estimated_difficulty=item.get("estimated_difficulty", "medium"),
                    best_season=item.get("best_season", []),
                )
            )
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("parse_itineraries failed: %s. Raw (500 chars): %.500s", exc, raw)
        raise ValueError(f"Risposta LLM non valida: {exc}") from exc
