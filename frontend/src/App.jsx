import { useState, useEffect, useMemo } from 'react'
import SearchForm from './components/SearchForm'
import SmartSearchForm from './components/SmartSearchForm'
import Map from './components/Map'
import ResultsList from './components/ResultsList'
import ItineraryCard from './components/ItineraryCard'
import { fetchAirports, searchReverse, searchSmartMulti } from './services/api'
import './App.css'

// ── Smart loading progress ────────────────────────────────────────────────────

const SMART_STEPS = [
  'Calcolo area esplorabile…',
  'Generazione itinerari con AI…',
  'Verifica prezzi reali…',
  'Selezione e ranking top 5…',
]
const STEP_MS = [4000, 12000, 35000] // durata step 0, 1, 2

function SmartLoadingProgress() {
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (step >= SMART_STEPS.length - 1) return
    const t = setTimeout(() => setStep((s) => s + 1), STEP_MS[step])
    return () => clearTimeout(t)
  }, [step])

  return (
    <div className="smart-loading">
      <div className="spinner" />
      <div className="smart-steps">
        {SMART_STEPS.map((label, i) => (
          <div
            key={i}
            className={`smart-step${i < step ? ' done' : i === step ? ' active' : ''}`}
          >
            <span className="step-dot" />
            {label}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  const [mode, setMode] = useState('reverse') // 'reverse' | 'smart'
  const [airports, setAirports] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Reverse search state
  const [reverseResults, setReverseResults] = useState(null)
  const [destination, setDestination] = useState('')

  // Smart search state
  const [smartResults, setSmartResults] = useState(null)

  useEffect(() => {
    fetchAirports().then(setAirports).catch(() => {})
  }, [])

  // Lookup IATA → airport object (latitude, longitude, city) — used by Map in smart mode
  const airportMap = useMemo(
    () => Object.fromEntries(airports.map((a) => [a.iata_code, a])),
    [airports]
  )

  const handleReverseSearch = async (params) => {
    setLoading(true)
    setError(null)
    setReverseResults(null)
    setDestination(params.destination)
    try {
      const data = await searchReverse(params)
      setReverseResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSmartSearch = async (params) => {
    setLoading(true)
    setError(null)
    setSmartResults(null)
    try {
      const data = await searchSmartMulti(params)
      setSmartResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const switchMode = (newMode) => {
    setMode(newMode)
    setError(null)
  }

  const hasResults = mode === 'reverse' ? !!reverseResults : !!smartResults

  // ── Empty state icon (airplane SVG) ──────────────────────────────────────
  const PlaneIcon = (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.6 1.27h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.91a16 16 0 0 0 6 6l.91-.91a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
    </svg>
  )

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <h1>HopCraft</h1>
          <span className="tagline">Voli intelligenti</span>
        </div>
        <div className="mode-tabs">
          <button
            className={`mode-tab ${mode === 'reverse' ? 'active' : ''}`}
            onClick={() => switchMode('reverse')}
          >
            Reverse Search
          </button>
          <button
            className={`mode-tab ${mode === 'smart' ? 'active' : ''}`}
            onClick={() => switchMode('smart')}
          >
            Smart Multi-City
          </button>
        </div>
      </header>

      <main className="main">
        {mode === 'reverse' && (
          <SearchForm airports={airports} onSearch={handleReverseSearch} loading={loading} />
        )}
        {mode === 'smart' && (
          <SmartSearchForm airports={airports} onSearch={handleSmartSearch} loading={loading} />
        )}

        {error && (
          <div className="error-bar">
            <span>{error}</span>
            <button className="error-dismiss" onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {!hasResults && !loading && !error && (
          <div className="empty-state">
            {PlaneIcon}
            <p>
              {mode === 'reverse'
                ? 'Inserisci una destinazione e un range di date per cercare i voli disponibili da tutta Europa.'
                : 'Inserisci origine, durata e budget. La AI proporrà itinerari multi-città ottimizzati (~30-60 sec).'}
            </p>
          </div>
        )}

        {loading && (
          mode === 'smart'
            ? <SmartLoadingProgress />
            : (
              <div className="loading-simple">
                <div className="spinner" />
                <p>Ricerca in corso…</p>
              </div>
            )
        )}

        {/* ── Reverse results ────────────────────────────────────────────── */}
        {mode === 'reverse' && reverseResults && (
          <div className="results-layout">
            <Map results={reverseResults.results} destination={destination} />
            <ResultsList
              results={reverseResults.results}
              cached={reverseResults.cached}
              destination={destination}
            />
          </div>
        )}

        {/* ── Smart results ──────────────────────────────────────────────── */}
        {mode === 'smart' && smartResults && (
          <div className="results-layout">
            <Map itineraries={smartResults.itineraries} airportMap={airportMap} />
            <div className="itinerary-list">
              <div className="results-header">
                <span>
                  {smartResults.itineraries.length} itinerari da{' '}
                  <strong>{smartResults.origin}</strong>
                </span>
              </div>
              <div className="itinerary-scroll">
                {smartResults.itineraries.map((it) => (
                  <ItineraryCard key={it.rank} itinerary={it} travelers={2} />
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
