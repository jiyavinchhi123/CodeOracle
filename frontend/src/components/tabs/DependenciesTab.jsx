import DependencyGraphView from '../DependencyGraphView'

export default function DependenciesTab({ graph }) {
  return (
    <div className="graph-container">
      <DependencyGraphView graph={graph} />
    </div>
  )
}
