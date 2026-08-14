export default function BreakingChangesTab({ report }) {
  if (!report) return <p>No breaking change analysis available.</p>

  return (
    <div>
      <p style={{ color: '#64748b' }}>{report.summary}</p>

      {!report.changes?.length && (
        <p style={{ color: '#166534' }}>No breaking changes detected.</p>
      )}

      {report.changes?.map((change, i) => (
        <div className="module-card" key={i}>
          <h4>
            <span className={`severity-${change.severity}`}>{change.severity.toUpperCase()}</span>
            {' — '}
            {change.title}
          </h4>
          <p>{change.description}</p>
          {change.affected_files?.length > 0 && (
            <p style={{ fontSize: 13 }}>
              <strong>Affected:</strong> {change.affected_files.join(', ')}
            </p>
          )}
          {change.recommendation && (
            <p style={{ fontSize: 13, color: '#475569' }}>
              <strong>Recommendation:</strong> {change.recommendation}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
