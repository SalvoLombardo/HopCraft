const BASE = '/api/v1'

/**
 * Ritorna la lista di tutti gli aeroporti attivi (usata per l'autocomplete).
 */
export async function fetchAirports() {
  const res = await fetch(`${BASE}/airports`)
  if (!res.ok) throw new Error('Impossibile caricare la lista aeroporti')
  return res.json()
}

/**
 * Ricerca inversa: voli da tutta Europa verso una destinazione specifica.
 *
 * @param {object} params
 * @param {string} params.destination  - Codice IATA (es. "CTA")
 * @param {string} params.dateFrom     - Data partenza minima (YYYY-MM-DD)
 * @param {string} params.dateTo       - Data partenza massima (YYYY-MM-DD)
 * @param {boolean} params.directOnly  - Solo voli diretti
 * @param {number} [params.maxResults] - Max risultati (default 50)
 */
export async function searchReverse({ destination, dateFrom, dateTo, directOnly, maxResults = 50 }) {
  const params = new URLSearchParams({
    destination,
    date_from: dateFrom,
    date_to: dateTo,
    direct_only: String(directOnly),
    max_results: String(maxResults),
  })

  const res = await fetch(`${BASE}/search/reverse?${params}`)

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `Errore ${res.status}`)
  }

  return res.json()
}

/**
 * Smart Multi-City: propone itinerari multi-città ottimizzati via AI.
 */
export async function searchSmartMulti({ origin, tripDurationDays, budgetPerPerson, travelers, dateFrom, dateTo, directOnly }) {
  const res = await fetch(`${BASE}/search/smart-multi`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin,
      trip_duration_days: tripDurationDays,
      budget_per_person_eur: budgetPerPerson,
      travelers,
      date_from: dateFrom,
      date_to: dateTo,
      direct_only: directOnly,
    }),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body.detail || `Errore ${res.status}`)
  }

  return res.json()
}
