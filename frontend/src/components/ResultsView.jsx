import { useState } from 'react'
import FileTree from './FileTree'
import CodeViewer from './CodeViewer'
import OverviewTab from './tabs/OverviewTab'
import ExplanationTab from './tabs/ExplanationTab'
import DependenciesTab from './tabs/DependenciesTab'
import TestsTab from './tabs/TestsTab'
import ModernizeTab from './tabs/ModernizeTab'
import BreakingChangesTab from './tabs/BreakingChangesTab'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'explanation', label: 'Explanation' },
  { id: 'dependencies', label: 'Dependencies' },
  { id: 'tests', label: 'Tests' },
  { id: 'modernize', label: 'Modernize' },
  { id: 'breaking', label: 'Breaking Changes' },
]

export default function ResultsView({ result }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [selectedFile, setSelectedFile] = useState(null)

  const contents = result.file_contents || {}
  const firstFile = Object.keys(contents)[0] || null
  const currentFile = selectedFile || firstFile
  const currentContent = currentFile ? contents[currentFile] : ''

  return (
    <div className="results-panel">
      <div className="tabs" role="tablist" aria-label="Analysis results">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            className={`tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="panel" role="tabpanel">
        {activeTab === 'overview' && (
          <>
            <OverviewTab summary={result.summary} />
            <div className="layout-split">
              <FileTree
                tree={result.file_tree}
                onSelect={setSelectedFile}
                selectedPath={currentFile}
              />
              <CodeViewer content={currentContent} path={currentFile} />
            </div>
          </>
        )}

        {activeTab === 'explanation' && <ExplanationTab modules={result.modules} />}
        {activeTab === 'dependencies' && <DependenciesTab graph={result.dependency_graph} />}
        {activeTab === 'tests' && (
          <TestsTab tests={result.generated_tests} results={result.test_results} />
        )}
        {activeTab === 'modernize' && <ModernizeTab modernization={result.modernization} />}
        {activeTab === 'breaking' && <BreakingChangesTab report={result.breaking_changes} />}
      </div>
    </div>
  )
}
