import { useState } from 'react'

export default function ModernizeTab({ modernization }) {
  const [selectedIdx, setSelectedIdx] = useState(0)

  if (!modernization?.files?.length) {
    return <p>No modernization suggestions available.</p>
  }

  const file = modernization.files[selectedIdx]

  return (
    <div>
      <p style={{ color: '#64748b' }}>{modernization.overall_summary}</p>

      <div style={{ marginBottom: 16 }}>
        {modernization.files.map((f, i) => (
          <button
            key={f.original_path}
            className={`tab ${selectedIdx === i ? 'active' : ''}`}
            style={{ display: 'inline-block' }}
            onClick={() => setSelectedIdx(i)}
          >
            {f.original_path}
          </button>
        ))}
      </div>

      <div className="module-card">
        <h4>{file.original_path} → {file.refactored_path}</h4>
        <p>{file.explanation}</p>
        {file.changes_summary?.length > 0 && (
          <ul>
            {file.changes_summary.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="compare-grid">
        <div className="compare-panel">
          <h5>Original</h5>
          <div className="code-viewer">
            <pre>{file.original_content}</pre>
          </div>
        </div>
        <div className="compare-panel">
          <h5>Refactored</h5>
          <div className="code-viewer">
            <pre>{file.refactored_content}</pre>
          </div>
        </div>
      </div>
    </div>
  )
}
