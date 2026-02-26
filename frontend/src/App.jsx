import { useState, useEffect, useMemo } from 'react'
import SearchForm from './components/SearchForm'
import SmartSearchForm from './components/SmartSearchForm'
import Map from './components/Map'
import ResultsList from './components/ResultsList'
import ItineraryCard from './components/ItineraryCard'
import { fetchAirports, searchReverse, searchSmartMulti } from './services/api'
import './App.css'

export default function App() {
  const [mode, setMode] = useState('reverse')  // 'reverse' | 'smart'
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

  return (
    <div className="app">
      <header className="header">
        <h1>HopCraft</h1>
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

        {error && <div className="error-bar">{error}</div>}

        {!hasResults && !loading && !error && (
          <div className="empty-state">
            {mode === 'reverse'
              ? 'Inserisci una destinazione e un range di date per cercare i voli.'
              : 'Inserisci origine, durata e budget. La AI proporrà itinerari multi-città (~30-60 sec).'}
          </div>
        )}

        {loading && (
          <div className="empty-state">
            {mode === 'smart'
              ? 'Analisi AI in corso e verifica prezzi reali… (~30-60 secondi)'
              : 'Ricerca in corso…'}
          </div>
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
