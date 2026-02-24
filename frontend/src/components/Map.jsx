import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'

const PRICE_TIERS = [
  { max: 50,  color: '#2ecc71', label: '<€50' },
  { max: 100, color: '#f1c40f', label: '€50-100' },
  { max: 150, color: '#e67e22', label: '€100-150' },
  { max: Infinity, color: '#e74c3c', label: '>€150' },
]

function priceColor(price) {
  return (PRICE_TIERS.find((t) => price < t.max) ?? PRICE_TIERS.at(-1)).color
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

export default function Map({ results, destination }) {
  return (
    <div className="map-wrapper">
      <div className="price-legend">
        {PRICE_TIERS.map((t) => (
          <span key={t.label} style={{ color: t.color }}>
            ● {t.label}
          </span>
        ))}
      </div>

      <MapContainer center={[50, 15]} zoom={4} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {results.map((r, i) => (
          <CircleMarker
            key={i}
            center={[r.latitude, r.longitude]}
            radius={9}
            fillColor={priceColor(r.price_eur)}
            color="#fff"
            weight={1.5}
            fillOpacity={0.88}
          >
            <Popup>
              <strong>
                {r.origin_city} ({r.origin})
              </strong>{' '}
              → {destination}
              <br />
              <strong style={{ fontSize: '1.1em' }}>€{r.price_eur.toFixed(2)}</strong> —{' '}
              {r.airline}
              <br />
              {formatDeparture(r.departure)}
              <br />
              {r.direct ? (
                <span style={{ color: '#27ae60' }}>✈ Diretto</span>
              ) : (
                formatDuration(r.duration_minutes)
              )}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
