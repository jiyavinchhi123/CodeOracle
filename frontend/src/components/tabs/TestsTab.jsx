export default function TestsTab({ tests, results }) {
  return (
    <div>
      {results && (
        <div style={{ marginBottom: 24 }}>
          <h4>Execution Results</h4>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="label">Passed</div>
              <div className="value" style={{ color: '#166534' }}>{results.passed}</div>
            </div>
            <div className="stat-card">
              <div className="label">Failed</div>
              <div className="value" style={{ color: '#991b1b' }}>{results.failed}</div>
            </div>
            <div className="stat-card">
              <div className="label">Errors</div>
              <div className="value" style={{ color: '#991b1b' }}>{results.errors}</div>
            </div>
            <div className="stat-card">
              <div className="label">Skipped</div>
              <div className="value">{results.skipped}</div>
            </div>
            {results.coverage_percent != null && (
              <div className="stat-card">
                <div className="label">Coverage</div>
                <div className="value">{results.coverage_percent.toFixed(1)}%</div>
              </div>
            )}
          </div>
          <p style={{ fontSize: 13, color: '#64748b' }}>{results.execution_note}</p>
          {results.tests?.map((t, i) => (
            <div className={`test-result ${t.status}`} key={i}>
              {t.name}: {t.status} {t.message && `— ${t.message}`}
            </div>
          ))}
        </div>
      )}

      <h4>Generated Tests</h4>
      {!tests?.length && <p>No tests generated.</p>}
      {tests?.map((t) => (
        <div className="module-card" key={t.test_file}>
          <h4>{t.test_file}</h4>
          <p style={{ fontSize: 13, color: '#64748b' }}>
            Source: {t.source_file} · Framework: {t.framework}
          </p>
          <div className="code-viewer">
            <pre>{t.content}</pre>
          </div>
        </div>
      ))}
    </div>
  )
}
