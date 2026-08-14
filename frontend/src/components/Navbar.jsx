import { SITE } from '../config/site'

export default function Navbar({ hasResults }) {
  return (
    <header className="site-header">
      <nav className="navbar" aria-label="Main">
        <div className="nav-inner">
          <a href="#top" className="brand">
            <div className="logo" aria-hidden>CO</div>
            <div className="brand-text">
              <div className="brand-title">{SITE.name}</div>
              <div className="brand-sub">{SITE.tagline}</div>
            </div>
          </a>

          <div className="nav-actions">
            <a href="#overview" className="nav-link">Features</a>
            <a href="#demo" className="nav-link">How it works</a>
            <a href="#upload" className="nav-link">Upload</a>
            {hasResults && (
              <a href="#results" className="nav-link nav-link-accent">Results</a>
            )}
            <a
              href={SITE.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="nav-cta"
            >
              GitHub
            </a>
          </div>
        </div>
      </nav>
    </header>
  )
}
