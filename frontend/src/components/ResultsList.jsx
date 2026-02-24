import { useState } from 'react'

const SORTS = {
  price: (a, b) => a.price_eur - b.price_eur,
  duration: (a, b) => a.duration_minutes - b.duration_minutes,
  departure: (a, b) => new Date(a.departure) - new Date(b.departure),
}

function formatDuration(minutes) {
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

function formatDeparture(iso) {
  return new Date(iso).toLocaleString('it-IT', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function ResultsList({ results, cached, destination }) {
  const [sortBy, setSortBy] = useState('price')

  const sorted = [...results].sort(SORTS[sortBy])

  return (
    <div className="results-list">
      <div className="results-header">
        <span>
          {results.length} voli → {destination}
          {cached && <span className="result-cached">(cache)</span>}
        </span>
        <div className="sort-controls">
          <label htmlFor="sort-select">Ordina</label>
          <select
            id="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="price">Prezzo</option>
            <option value="duration">Durata</option>
            <option value="departure">Partenza</option>
          </select>
        </div>
      </div>

      <ul>
        {sorted.map((r, i) => (
          <li key={i} className="result-item">
            <div className="result-main">
              <span className="result-city">{r.origin_city}</span>
              <span className="result-iata">({r.origin})</span>
              <span className="result-price">€{r.price_eur.toFixed(2)}</span>
            </div>
            <div className="result-detail">
              {r.airline} · {formatDeparture(r.departure)} ·{' '}
              {r.direct ? (
                <span className="badge-direct">Diretto</span>
              ) : (
                formatDuration(r.duration_minutes)
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
