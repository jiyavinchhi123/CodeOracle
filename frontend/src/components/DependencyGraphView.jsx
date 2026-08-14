import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { computeNodeVisual, safeSvgId } from '../utils/graphNodeLabel'

const EDGE_COLORS = {
  import: '#2563eb',
  inherits: '#7c3aed',
  implements: '#db2777',
  calls: '#059669',
  uses: '#d97706',
}

function GraphNode({ node, pos, active, onSelect }) {
  const langColor =
    node.language === 'java' ? '#fef3c7' : node.language === 'python' ? '#dbeafe' : '#f1f5f9'
  const visual = computeNodeVisual(node.label, active)
  const clipId = `clip-${safeSvgId(node.id)}`

  return (
    <g
      transform={`translate(${pos.x},${pos.y})`}
      onClick={(ev) => {
        ev.stopPropagation()
        onSelect(node.id)
      }}
      style={{ cursor: 'pointer' }}
    >
      <title>{`${node.label}\n${node.path}`}</title>
      <circle
        r={visual.radius}
        fill={langColor}
        stroke={active ? '#1d4ed8' : '#64748b'}
        strokeWidth={active ? 2.5 : 1.5}
      />
      <clipPath id={clipId}>
        <circle r={Math.max(visual.radius - 2, 8)} />
      </clipPath>
      <g clipPath={`url(#${clipId})`} pointerEvents="none">
        {visual.lines.map((line, index) => (
          <text
            key={`${node.id}-line-${index}`}
            x={0}
            y={visual.startY + index * visual.lineHeight}
            textAnchor="middle"
            fontSize={visual.fontSize}
            fill="#0f172a"
            dominantBaseline="middle"
          >
            {line}
          </text>
        ))}
      </g>
    </g>
  )
}

function normalizeGraph(graph) {
  if (!graph) return { nodes: [], edges: [], stats: { total_nodes: 0, total_edges: 0, edge_type_counts: {} } }

  const nodes = (graph.nodes || []).map((n) => {
    if (typeof n === 'string') {
      return { id: n, path: n, label: n.split('/').pop(), language: '', kind: 'module' }
    }
    return n
  })

  const edges = graph.edges || []
  const stats = graph.stats || {
    total_nodes: nodes.length,
    total_edges: edges.length,
    edge_type_counts: edges.reduce((acc, e) => {
      acc[e.edge_type] = (acc[e.edge_type] || 0) + 1
      return acc
    }, {}),
  }

  return { nodes, edges, stats }
}

function useForceLayout(nodes, edges, width, height, enabled) {
  const [positions, setPositions] = useState({})

  useEffect(() => {
    if (!enabled || nodes.length === 0) return undefined

    const simNodes = nodes.map((n, i) => ({
      id: n.id,
      x: width / 2 + Math.cos((i / nodes.length) * Math.PI * 2) * Math.min(width, height) * 0.3,
      y: height / 2 + Math.sin((i / nodes.length) * Math.PI * 2) * Math.min(width, height) * 0.3,
      vx: 0,
      vy: 0,
    }))
    const nodeIndex = Object.fromEntries(simNodes.map((n) => [n.id, n]))
    const simEdges = edges
      .map((e) => ({ source: nodeIndex[e.source], target: nodeIndex[e.target] }))
      .filter((e) => e.source && e.target)

    let frame = 0
    const maxFrames = 120
    let rafId

    const tick = () => {
      for (let i = 0; i < simNodes.length; i++) {
        for (let j = i + 1; j < simNodes.length; j++) {
          const a = simNodes[i]
          const b = simNodes[j]
          let dx = a.x - b.x
          let dy = a.y - b.y
          let dist = Math.sqrt(dx * dx + dy * dy) || 1
          const force = 9000 / (dist * dist)
          dx = (dx / dist) * force
          dy = (dy / dist) * force
          a.vx += dx
          a.vy += dy
          b.vx -= dx
          b.vy -= dy
        }
      }

      simEdges.forEach(({ source, target }) => {
        let dx = target.x - source.x
        let dy = target.y - source.y
        let dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - 120) * 0.04
        dx = (dx / dist) * force
        dy = (dy / dist) * force
        source.vx += dx
        source.vy += dy
        target.vx -= dx
        target.vy -= dy
      })

      simNodes.forEach((n) => {
        n.vx += (width / 2 - n.x) * 0.002
        n.vy += (height / 2 - n.y) * 0.002
        n.vx *= 0.85
        n.vy *= 0.85
        n.x += n.vx
        n.y += n.vy
        n.x = Math.max(40, Math.min(width - 40, n.x))
        n.y = Math.max(40, Math.min(height - 40, n.y))
      })

      frame += 1
      if (frame % 8 === 0 || frame >= maxFrames) {
        const next = {}
        simNodes.forEach((n) => {
          next[n.id] = { x: n.x, y: n.y }
        })
        setPositions(next)
      }
      if (frame < maxFrames) {
        rafId = requestAnimationFrame(tick)
      }
    }

    rafId = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafId)
  }, [nodes, edges, width, height, enabled])

  return positions
}

export default function DependencyGraphView({ graph, onSelectFile }) {
  const normalized = useMemo(() => normalizeGraph(graph), [graph])
  const { nodes, edges, stats } = normalized
  const containerRef = useRef(null)
  const [size, setSize] = useState({ width: 900, height: 520 })
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 })
  const [selectedId, setSelectedId] = useState(null)
  const [dragging, setDragging] = useState(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return undefined
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ width: Math.max(320, width), height: Math.max(360, height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const positions = useForceLayout(nodes, edges, size.width, size.height, nodes.length > 0)

  const nodeById = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes])
  const incoming = useMemo(() => {
    if (!selectedId) return []
    return edges.filter((e) => e.target === selectedId)
  }, [edges, selectedId])
  const outgoing = useMemo(() => {
    if (!selectedId) return []
    return edges.filter((e) => e.source === selectedId)
  }, [edges, selectedId])

  const onWheel = useCallback((e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setTransform((t) => ({ ...t, k: Math.min(3, Math.max(0.25, t.k * delta)) }))
  }, [])

  const onMouseDown = (e) => {
    if (e.target.dataset.pan === 'true') {
      setDragging({ x: e.clientX, y: e.clientY, tx: transform.x, ty: transform.y })
    }
  }

  const onMouseMove = (e) => {
    if (!dragging) return
    setTransform((t) => ({
      ...t,
      x: dragging.tx + (e.clientX - dragging.x),
      y: dragging.ty + (e.clientY - dragging.y),
    }))
  }

  const onMouseUp = () => setDragging(null)

  const selectNode = (id) => {
    setSelectedId(id)
    const node = nodeById[id]
    if (node && onSelectFile) onSelectFile(node.path)
  }

  if (nodes.length === 0) {
    return <p>No dependency data available.</p>
  }

  const selected = selectedId ? nodeById[selectedId] : null

  return (
    <div className="dep-graph-layout">
      <div className="dep-stats">
        <div className="dep-stat-card">
          <span className="dep-stat-value">{stats.total_nodes ?? nodes.length}</span>
          <span className="dep-stat-label">Nodes</span>
        </div>
        <div className="dep-stat-card">
          <span className="dep-stat-value">{stats.total_edges ?? edges.length}</span>
          <span className="dep-stat-label">Edges</span>
        </div>
        {Object.entries(stats.edge_type_counts || {}).map(([type, count]) => (
          <div className="dep-stat-card" key={type}>
            <span className="dep-stat-value">{count}</span>
            <span className="dep-stat-label">{type}</span>
          </div>
        ))}
      </div>

      <div className="dep-graph-main">
        <div
          className="dep-graph-canvas-wrap"
          ref={containerRef}
          onWheel={onWheel}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          <svg width={size.width} height={size.height} className="dep-graph-svg" data-pan="true">
            <rect width="100%" height="100%" fill="#f8fafc" data-pan="true" />
            <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
              {edges.map((e, i) => {
                const from = positions[e.source]
                const to = positions[e.target]
                if (!from || !to) return null
                const color = EDGE_COLORS[e.edge_type] || '#94a3b8'
                const mx = (from.x + to.x) / 2
                const my = (from.y + to.y) / 2
                return (
                  <g key={`${e.source}-${e.target}-${e.edge_type}-${i}`}>
                    <line
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      stroke={color}
                      strokeWidth={selectedId && (e.source === selectedId || e.target === selectedId) ? 2.5 : 1.5}
                      strokeOpacity={selectedId && e.source !== selectedId && e.target !== selectedId ? 0.25 : 0.75}
                      markerEnd="url(#dep-arrow)"
                    />
                    <text x={mx} y={my - 4} fontSize={9} fill={color} textAnchor="middle">
                      {e.edge_type}
                    </text>
                  </g>
                )
              })}

              {nodes.map((n) => {
                const pos = positions[n.id]
                if (!pos) return null
                return (
                  <GraphNode
                    key={n.id}
                    node={n}
                    pos={pos}
                    active={selectedId === n.id}
                    onSelect={selectNode}
                  />
                )
              })}
            </g>
            <defs>
              <marker id="dep-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
                <path d="M0,0 L6,3 L0,6" fill="#94a3b8" />
              </marker>
            </defs>
          </svg>
          <div className="dep-graph-hint">Scroll to zoom · Drag background to pan · Click a node to inspect</div>
        </div>

        <aside className="dep-graph-sidebar">
          {selected ? (
            <>
              <h4>{selected.label}</h4>
              <p className="dep-node-path">{selected.path}</p>
              <p className="dep-node-meta">
                {selected.language && <span>{selected.language}</span>}
                {selected.kind && <span>{selected.kind}</span>}
              </p>

              <div className="dep-edge-section">
                <strong>Outgoing ({outgoing.length})</strong>
                {outgoing.length === 0 && <p className="dep-muted">No outgoing dependencies</p>}
                <ul>
                  {outgoing.map((e, i) => (
                    <li key={`out-${i}`}>
                      <span className="dep-edge-type">{e.edge_type}</span>
                      <button type="button" className="dep-link" onClick={() => selectNode(e.target)}>
                        {nodeById[e.target]?.label || e.target}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="dep-edge-section">
                <strong>Incoming ({incoming.length})</strong>
                {incoming.length === 0 && <p className="dep-muted">No incoming dependencies</p>}
                <ul>
                  {incoming.map((e, i) => (
                    <li key={`in-${i}`}>
                      <button type="button" className="dep-link" onClick={() => selectNode(e.source)}>
                        {nodeById[e.source]?.label || e.source}
                      </button>
                      <span className="dep-edge-type">{e.edge_type}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          ) : (
            <div className="dep-sidebar-empty">
              <p>Select a node to view its file path and dependencies.</p>
              <ul className="dep-node-list">
                {nodes.map((n) => (
                  <li key={n.id}>
                    <button type="button" className="dep-link" onClick={() => selectNode(n.id)}>
                      {n.label}
                    </button>
                    <span className="dep-muted">{n.path}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
