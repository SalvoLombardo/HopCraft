"""
LLM Provider Layer — classi astratte e utility condivise.

Il prompt è definito qui una sola volta: tutti i provider lo ricevono identico,
garantendo output coerente indipendentemente dal modello usato.
"""
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SuggestedItinerary:
    route: list[str]           # es. ["CTA", "ATH", "SOF", "BUD", "CTA"]
    reasoning: str
    estimated_difficulty: str  # "easy" | "medium" | "hard"
    best_season: list[str]     # es. ["apr", "mag", "giu"]


class LLMProvider(ABC):

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
        Genera itinerari multi-città candidati.

        Args:
            origin:              codice IATA aeroporto di partenza/ritorno
            duration_days:       durata totale viaggio in giorni
            budget_per_leg:      budget per tratta per persona in EUR
            season:              stagione di viaggio (es. "estate 2026")
            num_stops:           numero di tappe intermedie suggerite
            available_airports:  lista stringhe "IATA (Città)" degli aeroporti nel raggio
        """
        ...


# ---------------------------------------------------------------------------
# Prompt condiviso — identico per tutti i provider
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Sei un esperto di viaggi e rotte aeree low-cost in Europa.
Dato un punto di partenza, una durata, un budget per tratta e una lista
di aeroporti raggiungibili, genera 8-10 itinerari multi-città ottimizzati.

Rispondi SOLO in JSON, senza preambolo né markdown.
Formato:
[
  {
    "route": ["CTA", "ATH", "SOF", "BUD", "CTA"],
    "reasoning": "Rotta balcanica con ottime connessioni low-cost",
    "estimated_difficulty": "easy",
    "best_season": ["apr", "mag", "giu", "set", "ott"]
  }
]

Criteri:
- Privilegia rotte con connessioni low-cost note (Ryanair, Wizz Air, easyJet)
- Ogni tappa deve avere senso geografico (no zig-zag)
- Considera la stagionalità
- Rispetta il budget per tratta indicato
- L'ultimo volo deve tornare all'origine"""


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
        f"Origine: {origin}\n"
        f"Durata viaggio: {duration_days} giorni\n"
        f"Budget per tratta per persona: {budget_per_leg}€\n"
        f"Stagione: {season}\n"
        f"Numero tappe intermedie: {num_stops}\n"
        f"Aeroporti disponibili nel raggio: {airport_list}"
    )
    if provider_hint:
        prompt += f"\nVincolo provider: {provider_hint}"
    return prompt


def parse_itineraries(raw: str) -> list[SuggestedItinerary]:
    """
    Converte la risposta testuale del modello in lista di SuggestedItinerary.

    Gestisce il caso in cui il modello wrappa il JSON in markdown code blocks
    nonostante le istruzioni (comportamento comune su alcuni provider).
    """
    # Rimuove eventuali ```json ... ``` o ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    cleaned = match.group(1).strip() if match else raw.strip()

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
