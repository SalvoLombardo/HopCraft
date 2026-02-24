import { useState, useEffect } from 'react'
import SearchForm from './components/SearchForm'
import Map from './components/Map'
import ResultsList from './components/ResultsList'
import { fetchAirports, searchReverse } from './services/api'
import './App.css'

export default function App() {
  const [airports, setAirports] = useState([])
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [destination, setDestination] = useState('')

  useEffect(() => {
    fetchAirports()
      .then(setAirports)
      .catch(() => {})
  }, [])

  const handleSearch = async (params) => {
    setLoading(true)
    setError(null)
    setResults(null)
    setDestination(params.destination)
    try {
      const data = await searchReverse(params)
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>HopCraft</h1>
        <p>Cerca voli verso la tua destinazione da tutta Europa</p>
      </header>

      <main className="main">
        <SearchForm airports={airports} onSearch={handleSearch} loading={loading} />

        {error && <div className="error-bar">{error}</div>}

        {!results && !loading && !error && (
          <div className="empty-state">
            Inserisci una destinazione e un range di date per cercare i voli disponibili.
          </div>
        )}

        {loading && (
          <div className="empty-state">Ricerca in corso...</div>
        )}

        {results && (
          <div className="results-layout">
            <Map results={results.results} destination={destination} />
            <ResultsList
              results={results.results}
              cached={results.cached}
              destination={destination}
            />
          </div>
        )}
      </main>
    </div>
  )
}
