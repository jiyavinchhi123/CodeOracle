export default function FileTree({ tree, onSelect, selectedPath }) {
  if (!tree || Object.keys(tree).length === 0) {
    return <div className="file-tree">No files</div>
  }

  const renderNode = (name, node, prefix = '') => {
    if (node.__file__) {
      const path = node.path
      return (
        <li key={path}>
          <div
            className={`file-item ${selectedPath === path ? 'selected' : ''}`}
            onClick={() => onSelect(path)}
          >
            📄 {name}
          </div>
        </li>
      )
    }

    return (
      <li key={prefix + name}>
        <div style={{ fontWeight: 500, padding: '4px 0' }}>📁 {name}</div>
        <ul>{Object.entries(node).map(([k, v]) => renderNode(k, v, prefix + name + '/'))}</ul>
      </li>
    )
  }

  return (
    <div className="file-tree">
      <ul>{Object.entries(tree).map(([name, node]) => renderNode(name, node))}</ul>
    </div>
  )
}
