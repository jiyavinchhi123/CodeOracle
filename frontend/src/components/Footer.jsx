import { SITE } from '../config/site'

export default function Footer() {
  const year = new Date().getFullYear()

  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div className="logo logo-sm" aria-hidden>CO</div>
          <div>
            <strong>{SITE.name}</strong>
            <p>{SITE.tagline}</p>
          </div>
        </div>

        <nav className="footer-nav" aria-label="Footer">
          <div className="footer-col">
            <span className="footer-col-title">Product</span>
            <a href="#overview">Features</a>
            <a href="#demo">How it works</a>
            <a href="#upload">Analyze project</a>
            <a href="#results">Results</a>
          </div>
          <div className="footer-col">
            <span className="footer-col-title">Resources</span>
            <a href={SITE.githubUrl} target="_blank" rel="noopener noreferrer">GitHub repository</a>
            <a href={SITE.apiDocsUrl} target="_blank" rel="noopener noreferrer">API documentation</a>
            <a href={SITE.demoVideoUrl} target="_blank" rel="noopener noreferrer">Demo video</a>
          </div>
          <div className="footer-col">
            <span className="footer-col-title">Supported</span>
            <span className="footer-muted">Python (.py)</span>
            <span className="footer-muted">Java (.java)</span>
            <span className="footer-muted">Public GitHub repos</span>
          </div>
        </nav>
      </div>

      <div className="footer-bottom">
        <span>© {year} {SITE.name}. Built for legacy codebase modernization.</span>
        <a href={SITE.githubUrl} target="_blank" rel="noopener noreferrer" className="text-link">
          Star on GitHub
        </a>
      </div>
    </footer>
  )
}
