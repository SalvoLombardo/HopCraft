import { useState } from 'react'

function todayStr() {
  return new Date().toISOString().split('T')[0]
}

function addDays(dateStr, n) {
  const d = new Date(dateStr)
  d.setDate(d.getDate() + n)
  return d.toISOString().split('T')[0]
}

export default function SmartSearchForm({ airports, onSearch, loading }) {
  const [origin, setOrigin] = useState('')
  const [budget, setBudget] = useState(300)
  const [travelers, setTravelers] = useState(1)
  const [dateFrom, setDateFrom] = useState(() => addDays(todayStr(), 30))
  const [dateTo, setDateTo] = useState(() => addDays(todayStr(), 42))
  const [directOnly, setDirectOnly] = useState(false)

  const handleDateFromChange = (val) => {
    setDateFrom(val)
    if (dateTo <= val) setDateTo(addDays(val, 12))
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const orig = origin.trim().toUpperCase()
    if (orig.length !== 3) return
    const tripDays = Math.round((new Date(dateTo) - new Date(dateFrom)) / (1000 * 60 * 60 * 24))
    if (tripDays < 5 || tripDays > 25) return
    onSearch({ origin: orig, tripDurationDays: tripDays, budgetPerPerson: budget, travelers, dateFrom, dateTo, directOnly })
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <div className="form-group">
        <label htmlFor="smart-origin">Origine (IATA)</label>
        <input
          id="smart-origin"
          type="text"
          list="airports-datalist-smart"
          value={origin}
          onChange={(e) => setOrigin(e.target.value.slice(0, 3))}
          placeholder="Es: CTA"
          required
          style={{ width: 90 }}
        />
        <datalist id="airports-datalist-smart">
          {airports.map((a) => (
            <option key={a.iata_code} value={a.iata_code}>
              {a.city} — {a.name}
            </option>
          ))}
        </datalist>
      </div>

      <div className="form-group">
        <label htmlFor="budget">Budget/persona (€)</label>
        <input
          id="budget"
          type="number"
          value={budget}
          min={50}
          step={10}
          onChange={(e) => setBudget(Number(e.target.value))}
          required
          style={{ width: 95 }}
        />
      </div>

      <div className="form-group">
        <label htmlFor="travelers">Viaggiatori</label>
        <input
          id="travelers"
          type="number"
          value={travelers}
          min={1}
          max={9}
          onChange={(e) => setTravelers(Number(e.target.value))}
          required
          style={{ width: 60 }}
        />
      </div>

      <div className="form-group">
        <label htmlFor="smart-date-from">Partenza</label>
        <input
          id="smart-date-from"
          type="date"
          value={dateFrom}
          min={todayStr()}
          onChange={(e) => handleDateFromChange(e.target.value)}
          required
        />
      </div>

      <div className="form-group">
        <label htmlFor="smart-date-to">Rientro entro</label>
        <input
          id="smart-date-to"
          type="date"
          value={dateTo}
          min={addDays(dateFrom, 1)}
          onChange={(e) => setDateTo(e.target.value)}
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
          Solo diretti
        </label>
      </div>

      <button className="search-btn" type="submit" disabled={loading}>
        {loading ? 'Analisi AI...' : 'Trova itinerari'}
      </button>
    </form>
  )
}
