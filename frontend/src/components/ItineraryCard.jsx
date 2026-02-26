export const ROUTE_COLORS = ['#0984e3', '#e84393', '#00b894', '#e67e22', '#6c5ce7']

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

export default function ItineraryCard({ itinerary, travelers }) {
  const color = ROUTE_COLORS[(itinerary.rank - 1) % ROUTE_COLORS.length]

  return (
    <div className="itinerary-card">
      <div className="itinerary-header">
        <span className="itinerary-rank" style={{ background: color }}>
          #{itinerary.rank}
        </span>
        <span className="itinerary-route">{itinerary.route.join(' → ')}</span>
        <span className="itinerary-total" style={{ color }}>
          €{itinerary.total_price_per_person_eur.toFixed(0)}
          <span className="itinerary-per-person">/pers.</span>
        </span>
      </div>

      {travelers > 1 && (
        <div className="itinerary-all-travelers">
          Totale {travelers} pers.: <strong>€{itinerary.total_price_all_travelers_eur.toFixed(0)}</strong>
        </div>
      )}

      <ul className="itinerary-legs">
        {itinerary.legs.map((leg, i) => (
          <li key={i} className="itinerary-leg">
            <span className="leg-airports">
              {leg.from_airport} → {leg.to_airport}
            </span>
            <span className="leg-price">€{leg.price_per_person_eur.toFixed(0)}</span>
            <span className="leg-detail">
              {leg.airline} · {formatDeparture(leg.departure)} ·{' '}
              {leg.direct ? (
                <span className="badge-direct">Diretto</span>
              ) : (
                formatDuration(leg.duration_minutes)
              )}
            </span>
          </li>
        ))}
      </ul>

      {itinerary.suggested_days_per_stop.length > 0 && (
        <div className="itinerary-days">
          {itinerary.route.slice(1, -1).map((iata, i) => (
            <span key={iata} className="days-badge">
              {iata} {itinerary.suggested_days_per_stop[i]}gg
            </span>
          ))}
        </div>
      )}

      {itinerary.ai_notes && (
        <p className="itinerary-notes">{itinerary.ai_notes}</p>
      )}
    </div>
  )
}
