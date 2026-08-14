export default function OverviewTab({ summary }) {
  if (!summary) return <p className="empty-state">No summary available.</p>

  return (
    <>
      <h3 className="panel-title">{summary.name}</h3>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="label">Total Files</div>
          <div className="value">{summary.total_files}</div>
        </div>
        <div className="stat-card">
          <div className="label">Total Lines</div>
          <div className="value">{summary.total_lines?.toLocaleString()}</div>
        </div>
        {summary.languages?.map((lang) => (
          <div className="stat-card" key={lang.language}>
            <div className="label">{lang.language}</div>
            <div className="value">{lang.file_count}</div>
            <div className="stat-sub">{lang.line_count?.toLocaleString()} lines</div>
          </div>
        ))}
      </div>

      {summary.files?.length > 0 && (
        <>
          <h4 className="panel-subtitle">Files</h4>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Path</th>
                  <th>Language</th>
                  <th>Lines</th>
                </tr>
              </thead>
              <tbody>
                {summary.files.map((f) => (
                  <tr key={f.path}>
                    <td><code className="path-cell">{f.path}</code></td>
                    <td>{f.language}</td>
                    <td>{f.line_count?.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
