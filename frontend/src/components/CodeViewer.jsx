export default function CodeViewer({ content, path }) {
  const lines = content ? content.split('\n') : []

  return (
    <div className="code-viewer">
      {path && (
        <div className="code-viewer-header">
          <span className="code-viewer-path">{path}</span>
          {lines.length > 0 && (
            <span className="code-viewer-meta">{lines.length} lines</span>
          )}
        </div>
      )}
      <pre>
        {content || `Select a file to view${path ? `: ${path}` : ''}`}
      </pre>
    </div>
  )
}
