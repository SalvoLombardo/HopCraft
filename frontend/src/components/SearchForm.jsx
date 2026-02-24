import { useState } from 'react'

function todayStr() {
  return new Date().toISOString().split('T')[0]
}

function addDays(dateStr, n) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + n)
  return d.toISOString().split('T')[0]
}

export default function SearchForm({ airports, onSearch, loading }) {
  const [destination, setDestination] = useState('')
  const [dateFrom, setDateFrom] = useState(todayStr)
  const [dateTo, setDateTo] = useState(() => addDays(todayStr(), 3))
  const [directOnly, setDirectOnly] = useState(false)

  const handleDateFromChange = (val) => {
    setDateFrom(val)
    // Mantieni dateTo >= dateFrom
    if (dateTo < val) setDateTo(val)
  }

  const handleDateToChange = (val) => {
    // Il backend accetta max 6 giorni di range
    const maxTo = addDays(dateFrom, 6)
    setDateTo(val > maxTo ? maxTo : val)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const dest = destination.trim().toUpperCase()
    if (dest.length !== 3) return
    onSearch({ destination: dest, dateFrom, dateTo, directOnly })
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="dest">Destinazione (IATA)</label>
        <input
          id="dest"
          type="text"
          list="airports-datalist"
          value={destination}
          onChange={(e) => setDestination(e.target.value.slice(0, 3))}
          placeholder="Es: CTA"
          required
          style={{ width: 90 }}
        />
        <datalist id="airports-datalist">
          {airports.map((a) => (
            <option key={a.iata_code} value={a.iata_code}>
              {a.city} — {a.name}
            </option>
          ))}
        </datalist>
      </div>

      <div className="form-group">
        <label htmlFor="date-from">Data da</label>
        <input
          id="date-from"
          type="date"
          value={dateFrom}
          min={todayStr()}
          onChange={(e) => handleDateFromChange(e.target.value)}
          required
        />
      </div>

      <div className="form-group">
        <label htmlFor="date-to">Data a (max +6 gg)</label>
        <input
          id="date-to"
          type="date"
          value={dateTo}
          min={dateFrom}
          max={addDays(dateFrom, 6)}
          onChange={(e) => handleDateToChange(e.target.value)}
          required
        />
      </div>

      <div className="form-group checkbox">
        <label>
          <input
            type="checkbox"
            checked={directOnly}
            onChange={(e) => setDirectOnly(e.target.checked)}
          />
          Solo voli diretti
        </label>
      </div>

      <button className="search-btn" type="submit" disabled={loading}>
        {loading ? 'Ricerca...' : 'Cerca voli'}
      </button>
    </form>
  )
}
