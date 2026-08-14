function NLDetailView({ nl, fallback }) {
  const detail = nl || {}
  const hasStructured =
    detail.purpose ||
    detail.how_it_works ||
    detail.input_desc ||
    detail.output_desc ||
    detail.important_behavior

  if (!hasStructured && fallback) {
    return <p>{fallback}</p>
  }

  return (
    <dl className="nl-detail">
      {detail.purpose && (
        <>
          <dt>Purpose</dt>
          <dd>{detail.purpose}</dd>
        </>
      )}
      {detail.how_it_works && (
        <>
          <dt>How it works</dt>
          <dd>{detail.how_it_works}</dd>
        </>
      )}
      {detail.input_desc && (
        <>
          <dt>Input</dt>
          <dd>{detail.input_desc}</dd>
        </>
      )}
      {detail.output_desc && (
        <>
          <dt>Output</dt>
          <dd>{detail.output_desc}</dd>
        </>
      )}
      {detail.important_behavior && (
        <>
          <dt>Important behavior</dt>
          <dd>{detail.important_behavior}</dd>
        </>
      )}
      {detail.technical_detail && (
        <details className="technical-detail-block">
          <summary>Technical analysis</summary>
          <pre className="technical-detail">{detail.technical_detail}</pre>
        </details>
      )}
    </dl>
  )
}

function EntryBlock({ entry, label }) {
  return (
    <div className="entry">
      <strong>{label || entry.name}</strong>
      {entry.line_start > 0 && (
        <span style={{ color: '#94a3b8', marginLeft: 8 }}>
          L{entry.line_start}–{entry.line_end}
        </span>
      )}
      {entry.structural && (
        <div className="structural-block">
          <span className="section-label">Structural Analysis</span>
          <p>{entry.structural}</p>
        </div>
      )}
      <div className="nl-block">
        <span className="section-label">Natural Language Explanation</span>
        <NLDetailView nl={entry.nl} fallback={entry.explanation} />
      </div>
      {entry.methods?.length > 0 && (
        <div style={{ marginTop: 8, paddingLeft: 12, borderLeft: '2px solid #e2e8f0' }}>
          <strong style={{ fontSize: 13 }}>Methods</strong>
          {entry.methods.map((m) => (
            <EntryBlock key={m.name} entry={m} label={m.name} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function ExplanationTab({ modules }) {
  if (!modules?.length) return <p>No explanations generated.</p>

  return (
    <div>
      {modules.map((mod) => (
        <div className="module-card" key={mod.path}>
          <h4>{mod.path}</h4>

          <div className="structural-block">
            <span className="section-label">Structural Analysis</span>
            <p>{mod.structural_summary || mod.summary}</p>
            {mod.imports?.length > 0 && (
              <p style={{ fontSize: 13, color: '#64748b' }}>
                <strong>Imports:</strong> {mod.imports.join('; ')}
              </p>
            )}
            {mod.line_count > 0 && (
              <p style={{ fontSize: 13, color: '#64748b' }}>
                <strong>Lines:</strong> {mod.line_count} · <strong>Language:</strong> {mod.language}
              </p>
            )}
          </div>

          <div className="nl-block">
            <span className="section-label">Natural Language Explanation</span>
            <NLDetailView nl={mod.nl} fallback={mod.explanation || mod.summary} />
            {mod.role_in_project && (
              <p style={{ marginTop: 12, fontSize: 13, color: '#475569' }}>
                <strong>Project role:</strong> {mod.role_in_project}
              </p>
            )}
          </div>

          {mod.classes?.length > 0 && (
            <>
              <h5 style={{ marginTop: 16 }}>Classes</h5>
              {mod.classes.map((c) => (
                <EntryBlock key={c.name} entry={c} />
              ))}
            </>
          )}

          {mod.functions?.length > 0 && (
            <>
              <h5 style={{ marginTop: 16 }}>Functions</h5>
              {mod.functions.map((f) => (
                <EntryBlock key={f.name} entry={f} />
              ))}
            </>
          )}
        </div>
      ))}
    </div>
  )
}
