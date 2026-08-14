import { useState, useEffect, useCallback, useRef } from 'react'
import UploadForm from './components/UploadForm'
import Navbar from './components/Navbar'
import ResultsView from './components/ResultsView'
import FeaturesSection from './components/FeaturesSection'
import HowItWorksSection from './components/HowItWorksSection'
import Footer from './components/Footer'

const API_BASE = '/api'

function parseApiError(data, fallback) {
  if (!data?.detail) return fallback
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    return data.detail.map((d) => d.msg || d.message || String(d)).join(', ')
  }
  return fallback
}

async function readJsonResponse(resp, fallbackMessage) {
  const text = await resp.text()
  try {
    return text ? JSON.parse(text) : {}
  } catch {
    throw new Error(fallbackMessage)
  }
}

export default function App() {
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [progress, setProgress] = useState(null)
  const [loading, setLoading] = useState(false)
  const pollRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const pollJob = useCallback(async (id) => {
    try {
      const resp = await fetch(`${API_BASE}/jobs/${id}`)
      const data = await readJsonResponse(resp, 'Server returned an invalid response. Try analyzing again.')
      if (!resp.ok) {
        throw new Error(parseApiError(data, 'Failed to fetch job status'))
      }
      setStatus(data.status)
      setProgress(data.progress || null)
      if (data.error) setError(data.error)
      if (data.result) setResult(data.result)
      return data.status
    } catch (err) {
      setError(err.message)
      setLoading(false)
      stopPolling()
      return 'failed'
    }
  }, [stopPolling])

  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') {
      stopPolling()
      return
    }

    stopPolling()
    pollRef.current = setInterval(async () => {
      const s = await pollJob(jobId)
      if (s === 'completed' || s === 'failed') {
        setLoading(false)
        stopPolling()
      }
    }, 1500)

    return stopPolling
  }, [jobId, status, pollJob, stopPolling])

  useEffect(() => {
    if (status === 'completed' && result) {
      const t = setTimeout(() => {
        document.getElementById('results')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 300)
      return () => clearTimeout(t)
    }
  }, [status, result])

  const handleAnalyze = async ({ type, file, githubUrl }) => {
    stopPolling()
    setError(null)
    setResult(null)
    setJobId(null)
    setStatus(null)
    setProgress(null)
    setLoading(true)

    try {
      let resp
      if (type === 'zip') {
        const form = new FormData()
        form.append('file', file)
        resp = await fetch(`${API_BASE}/analyze/zip`, { method: 'POST', body: form })
      } else {
        resp = await fetch(`${API_BASE}/analyze/github`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url: githubUrl }),
        })
      }

      const data = await readJsonResponse(resp, 'Analysis failed to start — server returned an invalid response.')
      if (!resp.ok) {
        throw new Error(parseApiError(data, 'Analysis failed to start'))
      }

      setJobId(data.job_id)
      setStatus(data.status)
      setProgress(data.progress || null)
      if (data.error) {
        setError(data.error)
        setLoading(false)
        return
      }
      await pollJob(data.job_id)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="app" id="top">
      <Navbar hasResults={Boolean(result && status === 'completed')} />

      <main>
        <section className="hero">
          <div className="hero-inner">
            <span className="hero-badge">Legacy code modernization</span>
            <h1>Understand. Modernize. Ship faster.</h1>
            <p className="hero-sub">
              CodeOracle analyzes Python and Java codebases — upload a ZIP or paste a GitHub URL to get
              explanations, dependency graphs, generated tests, and refactoring suggestions.
            </p>
            <div className="hero-ctas">
              <a href="#upload" className="btn btn-cta">Get started — Analyze project</a>
              <a href="#demo" className="btn btn-ghost">See how it works</a>
            </div>
          </div>
        </section>

        <FeaturesSection />

        <HowItWorksSection />

        <UploadForm id="upload" onAnalyze={handleAnalyze} loading={loading} progress={progress} />

        {error && (
          <div className="alert alert-error" role="alert">
            <strong>Analysis error</strong>
            <p>{error}</p>
          </div>
        )}

        {(jobId || loading) && (
          <div className="status-bar" role="status" aria-live="polite">
            {loading && <span className="status-spinner" aria-hidden />}
            {jobId && (
              <>
                Job <code>{jobId.slice(0, 8)}…</code>
                <span className="status-sep">·</span>
              </>
            )}
            Status: <strong>{status || 'starting'}</strong>
            {progress && <span className="status-progress">({progress})</span>}
            {result?.ai_mode && (
              <span className={`badge ${result.ai_mode === 'llm' ? 'badge-llm' : ''}`}>
                {result.ai_mode === 'llm' ? 'LLM mode' : 'Heuristic mode'}
              </span>
            )}
          </div>
        )}

        {result && status === 'completed' && (
          <section id="results" className="results-section">
            <div className="section-header section-header-compact">
              <span className="section-eyebrow">Analysis complete</span>
              <h2>Project results</h2>
            </div>
            <ResultsView result={result} />
          </section>
        )}
      </main>

      <Footer />
    </div>
  )
}
