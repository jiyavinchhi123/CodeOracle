import { useState, useRef } from 'react'

export default function UploadForm({ onAnalyze, loading, progress, id }) {
  const [file, setFile] = useState(null)
  const [githubUrl, setGithubUrl] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef(null)

  const handleFile = (f) => {
    setFile(f)
    if (f) setGithubUrl('')
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    const f = e.dataTransfer?.files?.[0]
    if (f) handleFile(f)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = () => setDragActive(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (file) onAnalyze({ type: 'zip', file })
    else if (githubUrl.trim()) onAnalyze({ type: 'github', githubUrl: githubUrl.trim() })
  }

  const canSubmit = (file || githubUrl.trim()) && !loading

  return (
    <form id={typeof id !== 'undefined' ? id : 'upload'} className="upload-card" onSubmit={handleSubmit}>
      <div className="upload-card-header">
        <h2>Analyze your project</h2>
        <p>
          Upload a ZIP archive or paste a public{' '}
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-link">
            GitHub
          </a>{' '}
          repository URL. New here?{' '}
          <a href="#demo" className="text-link">Watch the demo video</a>{' '}
          to see how it works.
        </p>
      </div>

      <div className="upload-grid">
        <div
          className={`drop-area ${dragActive ? 'drag-active' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => inputRef.current && inputRef.current.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault()
              inputRef.current?.click()
            }
          }}
          aria-label="Upload ZIP file"
        >
          <input
            ref={inputRef}
            type="file"
            accept=".zip"
            style={{ display: 'none' }}
            onChange={(e) => handleFile(e.target.files?.[0] || null)}
          />

          {!file ? (
            <div className="drop-empty">
              <div className="drop-icon" aria-hidden>
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 16V4m0 0l-4 4m4-4l4 4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div className="drop-text">Drag & drop a ZIP file here or click to browse</div>
              <div className="drop-sub">Max 50 MB · Python and Java source files</div>
            </div>
          ) : (
            <div className="drop-file">
              <span className="file-badge">ZIP</span>
              <strong>{file.name}</strong>
              <button
                type="button"
                className="btn btn-clear"
                onClick={(e) => {
                  e.stopPropagation()
                  handleFile(null)
                }}
              >
                Remove
              </button>
            </div>
          )}
        </div>

        <div className="upload-side">
          <label className="label" htmlFor="github-url">Or provide a GitHub URL</label>
          <input
            id="github-url"
            type="url"
            placeholder="https://github.com/owner/repo"
            value={githubUrl}
            onChange={(e) => {
              setGithubUrl(e.target.value)
              if (e.target.value) setFile(null)
            }}
            className="input-text"
          />

          <div className="actions">
            <button type="submit" className="btn btn-primary btn-lg" disabled={!canSubmit}>
              {loading ? (progress || 'Starting analysis…') : 'Analyze Project'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setFile(null)
                setGithubUrl('')
              }}
              disabled={loading}
            >
              Reset
            </button>
          </div>
        </div>
      </div>
    </form>
  )
}
