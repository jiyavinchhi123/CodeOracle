import { SITE } from '../config/site'

const STEPS = [
  {
    step: '01',
    title: 'Ingest your codebase',
    description: 'Drop a ZIP file or provide a public GitHub repository URL. CodeOracle validates, extracts, and indexes every source file safely.',
  },
  {
    step: '02',
    title: 'Run static analysis',
    description: 'AST parsing builds a dependency graph and structural metadata — classes, functions, imports, and line counts across Python and Java.',
  },
  {
    step: '03',
    title: 'Review AI insights',
    description: 'Browse tabbed results: overview stats, natural-language explanations, dependency graphs, generated tests, modernization diffs, and breaking-change warnings.',
  },
]

export default function HowItWorksSection() {
  return (
    <section id="demo" className="section how-section">
      <div className="section-header">
        <span className="section-eyebrow">How it works</span>
        <h2>From upload to insights in three steps</h2>
        <p className="section-desc">
          Watch the demo video below to see CodeOracle analyze a codebase end to end, or jump straight to the upload form to try it yourself.
        </p>
      </div>

      <div className="demo-video-wrap">
        <div className="demo-video-placeholder">
          <div className="play-icon-wrap">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="play-icon">
              <polygon points="6 3 20 12 6 21 6 3" fill="currentColor" />
            </svg>
          </div>
          <h3>See CodeOracle in Action</h3>
          <p className="placeholder-text">Watch a walkthrough of codebase analysis, visualization, and modernization.</p>
          <a
            href={SITE.demoVideoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary btn-lg btn-demo"
          >
            View Sample Demo
          </a>
        </div>
      </div>

      <ol className="steps-list">
        {STEPS.map((s) => (
          <li key={s.step} className="step-card">
            <span className="step-number">{s.step}</span>
            <div>
              <h3>{s.title}</h3>
              <p>{s.description}</p>
            </div>
          </li>
        ))}
      </ol>

      <div className="demo-cta">
        <a href="#upload" className="btn btn-primary">Try it now</a>
        <a href={SITE.demoVideoUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
          Watch on YouTube
        </a>
      </div>
    </section>
  )
}
