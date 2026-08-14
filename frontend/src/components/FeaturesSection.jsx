const FEATURES = [
  {
    icon: '🔍',
    title: 'Static analysis',
    description: 'Parses Python and Java source with AST and javalang to extract classes, functions, imports, and line counts.',
  },
  {
    icon: '🧠',
    title: 'AI explanations',
    description: 'Generates natural-language module summaries, class breakdowns, and role-in-project context for every file.',
  },
  {
    icon: '🔗',
    title: 'Dependency graph',
    description: 'Visualizes import, inheritance, and call relationships so you can see how modules connect.',
  },
  {
    icon: '🧪',
    title: 'Test generation',
    description: 'Produces pytest or JUnit tests and runs them in an isolated workspace with pass/fail reporting.',
  },
  {
    icon: '⚡',
    title: 'Modernization',
    description: 'Suggests refactored code stored side-by-side with originals — your source is never modified.',
  },
  {
    icon: '⚠️',
    title: 'Breaking changes',
    description: 'Compares original vs refactored symbols and flags API or parse regressions before you ship.',
  },
]

export default function FeaturesSection() {
  return (
    <section id="overview" className="section features-section">
      <div className="section-header">
        <span className="section-eyebrow">Capabilities</span>
        <h2>Everything you need to understand legacy code</h2>
        <p className="section-desc">
          Upload a ZIP archive or paste a public GitHub URL. CodeOracle ingests, analyzes, and returns
          actionable insights in a single workflow.
        </p>
      </div>

      <div className="features-grid">
        {FEATURES.map((f) => (
          <article key={f.title} className="feature-card">
            <span className="feature-icon" aria-hidden>{f.icon}</span>
            <h3>{f.title}</h3>
            <p>{f.description}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
